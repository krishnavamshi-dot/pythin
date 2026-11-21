import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from jobagent.models import Job
from jobagent import pipeline, db


def J(i, title, desc, loc="Remote, USA", remote=True, et="full_time", co=None):
    return Job("test", str(i), title, co or f"Co{i}", loc, f"http://x/{i}", desc, remote, "", et)


FIXTURES = [
    J(1, "Data Engineer", "Entry level. Build ETL pipelines with Python, SQL, Spark and Airflow on AWS. OPT/CPT welcome."),
    J(2, "Senior Data Engineer", "8+ years experience with Spark, Kafka, SQL, Python."),
    J(3, "Business Analyst", "SQL, Tableau, Power BI dashboards, stakeholder requirements. No sponsorship available."),
    J(4, "Data Scientist", "Python, statistics, scikit-learn, machine learning. Associate level.", "New York, NY", False),
    J(5, "Data Analyst Intern (CPT)", "CPT intern. SQL, Excel, Tableau dashboard work.", "Remote", True, "cpt"),
    J(6, "Data Engineer", "Python and SQL pipelines", "Berlin, Germany", False),
    J(7, "Java Developer", "Java, Spring, REST api, SQL microservices. Junior welcome.", "Austin, TX", False),
    J(8, "Marketing Manager", "Run campaigns", "Remote", True),
    J(9, "Data Engineer", "Entry level. Build ETL pipelines with Python, SQL, Spark and Airflow on AWS.", co="Co1"),  # dup of #1
]


def test_pipeline(tmp_path):
    con = pipeline.run(FIXTURES, str(tmp_path / "t.db"), log=lambda *_: None)
    rows = {r["key"]: r for r in db.top(con, "new", 50)}
    assert "test:1" in rows and rows["test:1"]["role"] == "Data Engineer"
    assert "test:2" not in rows          # senior
    assert "test:3" not in rows          # no sponsorship
    assert "test:4" in rows              # onsite US ok
    assert "test:5" in rows              # CPT tier kept
    assert "test:6" not in rows          # non-US
    assert "test:8" not in rows          # irrelevant
    assert "test:9" not in rows          # duplicate
    print(pipeline.digest(con))
