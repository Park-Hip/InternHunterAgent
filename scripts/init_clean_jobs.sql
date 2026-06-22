CREATE TABLE IF NOT EXISTS clean_jobs (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    description TEXT NOT NULL,
    tech_stack TEXT NOT NULL
);

INSERT INTO clean_jobs (id, title, company, description, tech_stack) VALUES
    (1, 'Backend Engineering Intern', 'Northstar Health', 'Help build internal APIs and job-processing workflows for a healthcare operations platform.', 'Python, FastAPI, PostgreSQL'),
    (2, 'Data Engineering Intern', 'SignalForge Labs', 'Support data ingestion, quality checks, and analytics pipelines for product telemetry.', 'Python, SQL, Airflow, dbt'),
    (3, 'Machine Learning Intern', 'Veridian Commerce', 'Work on ranking experiments and model evaluation for e-commerce search relevance.', 'Python, PyTorch, scikit-learn'),
    (4, 'Full Stack Engineering Intern', 'Atlas Fintech', 'Contribute to customer-facing dashboards and backend services for payments reconciliation.', 'TypeScript, React, FastAPI, PostgreSQL'),
    (5, 'Platform Engineering Intern', 'Cobalt Cloud', 'Assist with container automation, deployment workflows, and service reliability improvements.', 'Docker, Kubernetes, Python'),
    (6, 'Analytics Intern', 'BrightPath Mobility', 'Build reporting views and operational dashboards for transit usage and forecasting.', 'SQL, Python, Tableau'),
    (7, 'Software Engineering Intern', 'Northwind Research', 'Ship internal tools, improve developer workflows, and help maintain service integrations.', 'Python, FastAPI, SQL');
