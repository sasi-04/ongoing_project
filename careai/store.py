"""SQLite persistence: plans, audit trail, expert feedback, learned retrieval weights."""
import hashlib, json, sqlite3, time, uuid
from . import config, crypto


class Store:
    def __init__(self, path=None):
        path = path or config.DB_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS plans(id TEXT PRIMARY KEY, student_id TEXT, case_json TEXT, plan_json TEXT,
                                         status TEXT, created REAL);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT, plan_id TEXT, actor TEXT, role TEXT,
                                         action TEXT, detail TEXT, ts REAL, prev_hash TEXT, hash TEXT);
        CREATE TABLE IF NOT EXISTS users(username TEXT PRIMARY KEY, pw TEXT, role TEXT, students TEXT, created REAL);
        CREATE TABLE IF NOT EXISTS feedback(id INTEGER PRIMARY KEY AUTOINCREMENT, plan_id TEXT, item_id TEXT,
                                         intervention_id TEXT, decision TEXT, edited_text TEXT, role TEXT, ts REAL);
        CREATE TABLE IF NOT EXISTS weights(intervention_id TEXT PRIMARY KEY, weight REAL);
        CREATE TABLE IF NOT EXISTS router(agent TEXT PRIMARY KEY, params TEXT);
        CREATE TABLE IF NOT EXISTS replay(id INTEGER PRIMARY KEY AUTOINCREMENT, agent TEXT, x TEXT, label REAL);
        CREATE TABLE IF NOT EXISTS vitals(id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT, systolic INTEGER,
                                         diastolic INTEGER, pulse INTEGER, sleep_hours REAL, stress_level INTEGER,
                                         glucose REAL, notes TEXT, risk_flag TEXT, ts REAL);
        CREATE TABLE IF NOT EXISTS soap_notes(id TEXT PRIMARY KEY, plan_id TEXT, student_id TEXT, encounter_type TEXT,
                                             subjective TEXT, objective TEXT, assessment TEXT, plan TEXT,
                                             icd10_codes TEXT, cpt_codes TEXT, status TEXT, clinician TEXT,
                                             signature_hash TEXT, created REAL, signed_at REAL);
        """)

    def save_plan(self, case, plan):
        pid = uuid.uuid4().hex[:12]
        plan["plan_id"] = pid
        self.db.execute("INSERT INTO plans VALUES(?,?,?,?,?,?)",
                        (pid, case.student_id, crypto.enc(case.model_dump_json()), crypto.enc(json.dumps(plan)), plan["status"], time.time()))
        self.db.commit()
        return pid

    def get_plan(self, pid):
        r = self.db.execute("SELECT plan_json,status FROM plans WHERE id=?", (pid,)).fetchone()
        if not r:
            return None
        p = json.loads(crypto.dec(r[0])); p["status"] = r[1]
        return p

    def set_status(self, pid, status):
        self.db.execute("UPDATE plans SET status=? WHERE id=?", (status, pid)); self.db.commit()

    def log(self, pid, actor, role, action, detail=""):
        """Append-only, hash-chained audit entry (tamper-evident: editing any row breaks later hashes)."""
        row = self.db.execute("SELECT hash FROM audit ORDER BY id DESC LIMIT 1").fetchone()
        prev, ts = (row[0] if row else "GENESIS"), time.time()
        h = hashlib.sha256(f"{prev}|{pid}|{actor}|{role}|{action}|{detail}|{ts}".encode()).hexdigest()
        self.db.execute("INSERT INTO audit(plan_id,actor,role,action,detail,ts,prev_hash,hash) VALUES(?,?,?,?,?,?,?,?)",
                        (pid, actor, role, action, detail, ts, prev, h)); self.db.commit()

    def verify_audit(self):
        prev = "GENESIS"
        for i, pid, actor, role, action, detail, ts, ph, h in self.db.execute(
                "SELECT id,plan_id,actor,role,action,detail,ts,prev_hash,hash FROM audit ORDER BY id"):
            exp = hashlib.sha256(f"{prev}|{pid}|{actor}|{role}|{action}|{detail}|{ts}".encode()).hexdigest()
            if ph != prev or h != exp:
                return {"intact": False, "first_bad_row": i}
            prev = h
        return {"intact": True}

    def audit(self, pid):
        rows = self.db.execute("SELECT actor,role,action,detail,ts,hash FROM audit WHERE plan_id=? ORDER BY id", (pid,)).fetchall()
        return [dict(zip(("actor", "role", "action", "detail", "ts", "hash"), r)) for r in rows]

    def weights(self):
        return dict(self.db.execute("SELECT intervention_id, weight FROM weights").fetchall())

    def set_weight(self, iid, w):
        self.db.execute("INSERT INTO weights VALUES(?,?) ON CONFLICT(intervention_id) DO UPDATE SET weight=excluded.weight", (iid, w))
        self.db.commit()

    def add_feedback(self, pid, item_id, iid, decision, edited, role):
        self.db.execute("INSERT INTO feedback(plan_id,item_id,intervention_id,decision,edited_text,role,ts) VALUES(?,?,?,?,?,?,?)",
                        (pid, item_id, iid, decision, edited, role, time.time())); self.db.commit()

    def decisions(self, pid):
        rows = self.db.execute("SELECT item_id, decision FROM feedback WHERE plan_id=? ORDER BY id", (pid,)).fetchall()
        return dict(rows)  # latest decision per item wins

    def feedback_stats(self):
        rows = self.db.execute("SELECT decision, COUNT(*) FROM feedback GROUP BY decision").fetchall()
        d = dict(rows); n = sum(d.values())
        return {"counts": d, "total": n, "acceptance_rate": round(d.get("accept", 0) / n, 3) if n else None}

    # ---- learned router + replay buffer (paper Alg. 4)
    def router_weights(self):
        return {a: json.loads(p) for a, p in self.db.execute("SELECT agent, params FROM router").fetchall()}

    def set_router(self, agent, params):
        self.db.execute("INSERT INTO router VALUES(?,?) ON CONFLICT(agent) DO UPDATE SET params=excluded.params",
                        (agent, json.dumps(params))); self.db.commit()

    def add_replay(self, agent, x, label):
        self.db.execute("INSERT INTO replay(agent,x,label) VALUES(?,?,?)", (agent, json.dumps(x), label)); self.db.commit()

    def sample_replay(self, n):
        rows = self.db.execute("SELECT agent,x,label FROM replay ORDER BY RANDOM() LIMIT ?", (n,)).fetchall()
        return [(a, json.loads(x), l) for a, x, l in rows]

    def replay_size(self):
        return self.db.execute("SELECT COUNT(*) FROM replay").fetchone()[0]

    # ---- users
    def add_user(self, username, pw_hash, role, students):
        self.db.execute("INSERT INTO users VALUES(?,?,?,?,?)", (username, pw_hash, role, json.dumps(students), time.time()))
        self.db.commit()

    def get_user(self, username):
        r = self.db.execute("SELECT username,pw,role,students FROM users WHERE username=?", (username,)).fetchone()
        return {"username": r[0], "pw": r[1], "role": r[2], "students": json.loads(r[3])} if r else None

    def user_count(self):
        return self.db.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    def plan_student(self, pid):
        r = self.db.execute("SELECT student_id FROM plans WHERE id=?", (pid,)).fetchone()
        return r[0] if r else None

    def list_plans(self, students=None):
        rows = self.db.execute("SELECT id,student_id,status,created FROM plans ORDER BY created DESC LIMIT 200").fetchall()
        return [dict(zip(("plan_id", "student_id", "status", "created"), r)) for r in rows
                if not students or r[1] in students]

    # ---- vitals & biometric telemetry
    def add_vitals(self, student_id: str, systolic: int, diastolic: int, pulse: int, sleep_hours: float,
                   stress_level: int, glucose: float = 0.0, notes: str = "", risk_flag: str = "normal", ts: float = None):
        ts = ts or time.time()
        self.db.execute("INSERT INTO vitals(student_id,systolic,diastolic,pulse,sleep_hours,stress_level,glucose,notes,risk_flag,ts) VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (student_id, systolic, diastolic, pulse, sleep_hours, stress_level, glucose, notes, risk_flag, ts))
        self.db.commit()

    def get_vitals(self, student_id: str, limit: int = 50):
        rows = self.db.execute("SELECT id,student_id,systolic,diastolic,pulse,sleep_hours,stress_level,glucose,notes,risk_flag,ts FROM vitals WHERE student_id=? ORDER BY ts DESC LIMIT ?",
                               (student_id, limit)).fetchall()
        cols = ("id", "student_id", "systolic", "diastolic", "pulse", "sleep_hours", "stress_level", "glucose", "notes", "risk_flag", "ts")
        return [dict(zip(cols, r)) for r in rows]

    def update_user_pw(self, username: str, new_pw_hash: str):
        self.db.execute("UPDATE users SET pw=? WHERE username=?", (new_pw_hash, username))
        self.db.commit()

    def update_user_caseload(self, username: str, students: list):
        self.db.execute("UPDATE users SET students=? WHERE username=?", (json.dumps(students), username))
        self.db.commit()

    def list_users(self):
        rows = self.db.execute("SELECT username,role,students,created FROM users ORDER BY created DESC").fetchall()
        return [{"username": r[0], "role": r[1], "students": json.loads(r[2]), "created": r[3]} for r in rows]

    # ---- SOAP clinical encounter notes
    def save_soap_note(self, n: dict) -> str:
        nid = n.get("id") or ("SOAP-" + uuid.uuid4().hex[:8].upper())
        n["id"] = nid
        now = time.time()
        self.db.execute(
            "INSERT INTO soap_notes VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                nid,
                n.get("plan_id", ""),
                n.get("student_id", ""),
                n.get("encounter_type", "Comprehensive Clinical Consultation"),
                n.get("subjective", ""),
                n.get("objective", ""),
                n.get("assessment", ""),
                n.get("plan", ""),
                json.dumps(n.get("icd10_codes", [])),
                json.dumps(n.get("cpt_codes", [])),
                n.get("status", "draft"),
                n.get("clinician", ""),
                n.get("signature_hash", ""),
                n.get("created", now),
                n.get("signed_at", 0.0)
            )
        )
        self.db.commit()
        return nid

    def get_soap_note(self, nid: str):
        r = self.db.execute(
            "SELECT id,plan_id,student_id,encounter_type,subjective,objective,assessment,plan,icd10_codes,cpt_codes,status,clinician,signature_hash,created,signed_at FROM soap_notes WHERE id=?",
            (nid,)
        ).fetchone()
        if not r:
            return None
        return {
            "id": r[0],
            "plan_id": r[1],
            "student_id": r[2],
            "encounter_type": r[3],
            "subjective": r[4],
            "objective": r[5],
            "assessment": r[6],
            "plan": r[7],
            "icd10_codes": json.loads(r[8]),
            "cpt_codes": json.loads(r[9]),
            "status": r[10],
            "clinician": r[11],
            "signature_hash": r[12],
            "created": r[13],
            "signed_at": r[14]
        }

    def update_soap_note(self, nid: str, updates: dict):
        current = self.get_soap_note(nid)
        if not current:
            return None
        subj = updates.get("subjective", current["subjective"])
        obj = updates.get("objective", current["objective"])
        asm = updates.get("assessment", current["assessment"])
        pln = updates.get("plan", current["plan"])
        icd = json.dumps(updates.get("icd10_codes", current["icd10_codes"]))
        cpt = json.dumps(updates.get("cpt_codes", current["cpt_codes"]))
        self.db.execute(
            "UPDATE soap_notes SET subjective=?, objective=?, assessment=?, plan=?, icd10_codes=?, cpt_codes=? WHERE id=?",
            (subj, obj, asm, pln, icd, cpt, nid)
        )
        self.db.commit()
        return self.get_soap_note(nid)

    def sign_soap_note(self, nid: str, clinician: str, sig_hash: str):
        now = time.time()
        self.db.execute(
            "UPDATE soap_notes SET status='signed', clinician=?, signature_hash=?, signed_at=? WHERE id=?",
            (clinician, sig_hash, now, nid)
        )
        self.db.commit()
        return self.get_soap_note(nid)

    def list_soap_notes(self, student_id: str = None, limit: int = 50):
        if student_id:
            rows = self.db.execute(
                "SELECT id,plan_id,student_id,encounter_type,subjective,objective,assessment,plan,icd10_codes,cpt_codes,status,clinician,signature_hash,created,signed_at FROM soap_notes WHERE student_id=? ORDER BY created DESC LIMIT ?",
                (student_id, limit)
            ).fetchall()
        else:
            rows = self.db.execute(
                "SELECT id,plan_id,student_id,encounter_type,subjective,objective,assessment,plan,icd10_codes,cpt_codes,status,clinician,signature_hash,created,signed_at FROM soap_notes ORDER BY created DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return [
            {
                "id": r[0],
                "plan_id": r[1],
                "student_id": r[2],
                "encounter_type": r[3],
                "subjective": r[4],
                "objective": r[5],
                "assessment": r[6],
                "plan": r[7],
                "icd10_codes": json.loads(r[8]),
                "cpt_codes": json.loads(r[9]),
                "status": r[10],
                "clinician": r[11],
                "signature_hash": r[12],
                "created": r[13],
                "signed_at": r[14]
            }
            for r in rows
        ]
