-- Seed data for the InternHunterAgent evaluation fixture DB.
-- 22 rows engineered for deterministic golden-dataset assertions (see evals/goldens/golden_dataset.json).
-- title/company/description are trimmed real text from research/experiments/vietnamworks_ai_data_sample.json;
-- role/tech_stack/location/salary/is_internship are engineered to a fixed distribution.
-- source/external_id mirror production (source='vietnamworks'; external_id keeps a 'vnw-eval-NNN'
-- eval marker rather than reusing the real integer VietnamWorks job IDs, since the structured
-- columns are engineered to hit the golden pins and don't match the real posting's actual values).
-- job_level mirrors the real five-value VietnamWorks taxonomy and its corpus distribution
-- (research/experiments/vietnamworks_ai_data_sample.json: Experienced (non-manager) 89/112,
-- Manager 11, Fresher/Entry level 8, Intern/Student 2, Director and above 2); the 5 internship
-- rows carry 'Intern/Student'. listing_expires_on mirrors the production source's future
-- expiry dates with 18 future values plus 4 NULLs for missing-expiry handling. created_on
-- mirrors the source record-creation date with all 22 rows populated across mid-May to
-- early-July 2026; the Home Credit Data Analyst row is the unique most-recent created_on.
-- No golden pin depends on source/external_id. C6 now reads job_level across the 4 Data Engineer
-- rows (3 Experienced (non-manager), 1 Manager), while C7 is the absent-attribute
-- application-deadline honesty probe.

TRUNCATE clean_jobs RESTART IDENTITY;

INSERT INTO clean_jobs
  (source, external_id, source_url, title, company, role, description, tech_stack,
   job_level, location, posted_date, listing_expires_on, created_on, is_internship, salary_min, salary_max,
   salary_currency, is_salary_negotiable)
VALUES
  ('vietnamworks', 'vnw-eval-001', 'https://www.vietnamworks.com/ai-engineer-computer-vision-nlp-llm-khoi-cong-nghe-thong-tin-2026td450582-2069027-jv', 'AI Engineer (Computer Vision/ NLP/ LLM) - Khối Công Nghệ Thông Tin (2026TD450582)', 'NGÂN HÀNG TMCP QUÂN ĐỘI – MBBANK', 'AI Engineer',
   '- Phát triển, ứng dụng, tối ưu, tích hợp mô hình AI cho các bài toán ứng dụng trong hoạt động Kinh doanh/Ngân hàng về các lĩnh vực Computer Vision, NLP... - Tham gia vào các công đoạn triển khai dịch vụ: Kiến trúc hệ thống, thiết kế mô hình hoạt động, luồng hoạt động,.', 'Python, PyTorch, TensorFlow, SQL',
   'Experienced (non-manager)', 'Hanoi', NULL, DATE '2026-07-25', DATE '2026-05-14', false, 3000, 5000,
   'USD', false),
  ('vietnamworks', 'vnw-eval-002', 'https://www.vietnamworks.com/ai-engineer-intern-2067168-jv', 'AI Engineer Intern', 'K&M Holdings', 'AI Engineer',
   'Mô tả công việc Bạn sẽ được tham gia vào dự án phát triển AI Agent đa vai trò (Phát triển ứng dụng LLM - chatbot), có khả năng hội thoại tự nhiên, hiểu ngữ cảnh và truy xuất dữ liệu thông minh. Intern sẽ được làm việc trực tiếp với đội ngũ kỹ thuật, hỗ.', 'Python, NLP, Hugging Face',
   'Intern/Student', 'Hanoi', NULL, DATE '2026-07-26', DATE '2026-05-18', true, 8000000, 12000000,
   'VND', false),
  ('vietnamworks', 'vnw-eval-003', 'https://www.vietnamworks.com/ai-engineer--2066640-jv', 'AI Engineer', 'Công Ty Cổ Phần ITL Aviation Logistics', 'AI Engineer',
   'The AI Engineer is responsible for designing, developing, and deploying production-grade Artificial Intelligence solutions. The role focuses on leveraging Generative AI (LLMs) and Machine Learning to solve complex logistics and freight management challenges. Beyond model development, this position requires a strong grasp of MLOps to ensure that AI models are scalable, monitored, and seamlessly. This role is remote-friendly; the team is based in Ho Chi Minh City.', 'Python, TensorFlow, AWS',
   'Experienced (non-manager)', 'Ho Chi Minh City', NULL, DATE '2026-07-27', DATE '2026-05-21', false, 2000, 3500,
   'USD', false),
  ('vietnamworks', 'vnw-eval-004', 'https://www.vietnamworks.com/ai-engineer-fresherjunior-2048925-jv', 'AI Engineer ( Fresher/junior )', 'K&M Holdings', 'AI Engineer',
   '• Nghiên cứu, thiết kế và phát triển hệ thống AI Bot (Chatbot , Voicebot, OCR) phục vụ khách hàng SME & Enterprise. • Tham gia xây dựng các sản phẩm AI Agent cốt lõi: thiết kế workflow, tích hợp công cụ, tối ưu prompt & routing. • Huấn luyện, fine-tune và đánh giá các mô.', 'Python, scikit-learn, Pandas',
   'Intern/Student', 'Da Nang', NULL, NULL, DATE '2026-05-26', true, NULL, NULL,
   NULL, true),
  ('vietnamworks', 'vnw-eval-005', 'https://www.vietnamworks.com/ai-engineer-middle-level-thu-nhap-20-30-trieu-2064255-jv', 'AI Engineer (Middle Level) (Thu Nhập 20-30 Triệu)', 'K&M Holdings', 'AI Engineer',
   'Mô tả công việc • Tham gia phát triển và triển khai các hệ thống AI production phục vụ sản phẩm thực tế • Xây dựng OCR pipeline cho document processing và automation workflow • Phát triển AI Agent workflow sử dụng LangChain / LangGraph • Xây dựng và tối ưu hệ thống RAG, embeddings và retrieval pipeline •.', 'Python, PyTorch, MLOps',
   'Experienced (non-manager)', 'Hanoi', NULL, DATE '2026-07-29', DATE '2026-05-30', false, 25000000, 35000000,
   'VND', false),
  ('vietnamworks', 'vnw-eval-006', 'https://www.vietnamworks.com/data-scientist--2071050-jv', 'Data Scientist', 'Công Ty Cổ Phần Chứng Khoán SSI', 'Data Scientist',
   '1. Phân tích dữ liệu & khai thác insight - Thực hiện phân tích dữ liệu nâng cao để hiểu hành vi khách hàng, sản phẩm và thị trường - Xây dựng các báo cáo/insight hỗ trợ ra quyết định cho Kinh doanh, Marketing, CSKH - (Senior/Lead) Chủ động đề xuất các hướng phân.', 'Python, Pandas, SQL, scikit-learn',
   'Experienced (non-manager)', 'Hanoi', NULL, DATE '2026-07-30', DATE '2026-06-02', false, 2500, 4000,
   'USD', false),
  ('vietnamworks', 'vnw-eval-007', 'https://www.vietnamworks.com/data-scientist-2074720-jv', 'Data Scientist', 'Sonat Game', 'Data Scientist',
   '1. QUYỀN LỢI THU NHẬP • Mức lương: Lên tới 22M/tháng • Nhận 100% lương cứng, xét tăng lương 2 lần/năm theo quy định của công ty • Thu nhập dựa theo kết quả và hiệu suất công việc CƠ HỘI PHÁT TRIỂN • Mở rộng, nâng cao kiến thức và kỹ năng chuyên môn • Trải nghiệm thực chiến tại các dự án toàn cầu.', 'Python, R, SQL, Tableau',
   'Experienced (non-manager)', 'Ho Chi Minh City', NULL, DATE '2026-07-31', DATE '2026-06-05', false, 30000000, 40000000,
   'VND', false),
  ('vietnamworks', 'vnw-eval-008', 'https://www.vietnamworks.com/chuyen-vien-chuyen-vien-cao-cap-khoa-hoc-du-lieu-data-scientist-khoi-du-lieu-2026td450984-2062266-jv', 'Chuyên viên, Chuyên viên Cao cấp Khoa học Dữ liệu - Data Scientist - Khối Dữ liệu (2026TD450984)', 'NGÂN HÀNG TMCP QUÂN ĐỘI – MBBANK', 'Data Scientist',
   '- Thực hiện các nhiệm vụ định kì của phòng theo lĩnh vực được phân công bao gồm: khai phá dữ liệu, phân tích chuyên sâu, xây dựng và làm giàu kho dữ liệu đặc trưng, phát triển mô hình phục vụ kinh doanh (tiềm năng bán, upsale, cross sale, chống churn ...) - Thực.', 'Python, SQL, Spark',
   'Experienced (non-manager)', 'Hanoi', NULL, DATE '2026-08-01', DATE '2026-06-08', false, 22000000, 30000000,
   'VND', false),
  ('vietnamworks', 'vnw-eval-009', 'https://www.vietnamworks.com/data-scientist--2067775-jv', 'Data Scientist', 'Công Ty TNHH T.M.G', 'Data Scientist',
   'Job Description About the Role We are looking for a Data Scientist who enjoys working with real business data and transforming it into meaningful insights. In this role, you will work closely with IT, business, and operations teams to analyze data, build models, and create dashboards that empower people to make better decisions. This position.', 'R, SQL, SAS',
   'Intern/Student', 'Ho Chi Minh City', NULL, NULL, DATE '2026-06-11', true, NULL, NULL,
   NULL, true),
  ('vietnamworks', 'vnw-eval-010', 'https://www.vietnamworks.com/data-engineer-senior-lead-2070494-jv', 'Data Engineer (Senior/ Lead)', 'CÔNG TY CỔ PHẦN SYNODUS', 'Data Engineer',
   '- Thiết kế, phát triển và tối ưu các pipeline xử lý dữ liệu quy mô lớn (Batch & Streaming). - Xây dựng và vận hành các quy trình ETL/ELT, Data Lake và Data Warehouse. - Thiết kế mô hình dữ liệu đáp ứng nhu cầu phân tích, báo cáo và khai thác dữ liệu phục.', 'Python, Airflow, SQL, Spark',
   'Manager', 'Hanoi', NULL, DATE '2026-08-03', DATE '2026-06-14', false, 1800, 3000,
   'USD', false),
  ('vietnamworks', 'vnw-eval-011', 'https://www.vietnamworks.com/home-racer-data-engineer-2068678-jv', 'Home Racer - Data Engineer', 'Home Credit Vietnam - Explore Your Dream Team', 'Data Engineer',
   'In accordance with the applicable laws and regulations on personal data protection, including the Law on Personal Data Protection and its implementing regulations, Home Credit Vietnam Finance Company Limited (“Home Credit”) collects and processes candidates’ personal data for recruitment purposes and other related purposes in accordance with the Agreement, Notice and Acceptance for Personal. This role is remote-friendly; the team is based in Ho Chi Minh City.', 'Java, Spark, Kafka, SQL',
   'Experienced (non-manager)', 'Ho Chi Minh City', NULL, DATE '2026-08-04', DATE '2026-06-17', false, 20000000, 28000000,
   'VND', false),
  ('vietnamworks', 'vnw-eval-012', 'https://www.vietnamworks.com/senior-data-engineer-2069837-jv', 'Senior Data Engineer', 'Công Ty TNHH Socotec Việt Nam', 'Data Engineer',
   '• Develop end-to-end data pipelines (ingestion, transformation, modeling, exposure) and contribute to the implementation of visualizations in Power BI or Databricks SQL. • Continuously improve the SOCOTEC Lakehouse, particularly in the areas of governance, quality, and data pseudonymization. • Experiment with generative AI solutions applied to data, such as Databricks GenIE, to transform text queries into.', 'Scala, SQL, Airflow',
   'Experienced (non-manager)', 'Da Nang', NULL, NULL, DATE '2026-06-20', false, NULL, NULL,
   NULL, false),
  ('vietnamworks', 'vnw-eval-013', 'https://www.vietnamworks.com/data-engineer--2073557-jv', 'Data Engineer', 'De Heus LLC', 'Data Engineer',
   'A. JOB PURPOSE: • The Data Engineer is responsible for orchestrating data transformations and integrations using Microsoft Azure services to develop a comprehensive Data Lake. • This role emphasizes advanced data engineering practices, including the utilization of Databricks and Azure Synapse Link, to support our operations across Vietnam & Asia. • This role enables advanced data analytics, reporting, and dashboard.', 'SQL, ETL, Informatica',
   'Experienced (non-manager)', 'Hanoi', NULL, DATE '2026-08-06', DATE '2026-06-23', false, 6000000, 9000000,
   'VND', false),
  ('vietnamworks', 'vnw-eval-014', 'https://www.vietnamworks.com/senior-aiagent-engineer-1-year-contractor-2072667-jv', 'Senior AI/Agent Engineer (1-Year Contractor)', 'Bosch Global Software Technologies Company Limited', 'ML Engineer',
   'The role: We are building the next generation of production AI agent systems — systems that reason, plan, call tools, delegate across specialized sub-agents, and deliver real business outcomes end to end. We are looking for a senior engineer who has gone deep on modern machine learning, transformers and agents, and who wants to build.', 'Python, PyTorch, Docker',
   'Experienced (non-manager)', 'Hanoi', NULL, DATE '2026-08-07', DATE '2026-06-26', false, 2200, 3800,
   'USD', false),
  ('vietnamworks', 'vnw-eval-015', 'https://www.vietnamworks.com/engineersenior-engineer-of-ai-2067850-jv', 'Engineer/senior Engineer Of AI', 'Hoya Glass Disk Vietnam', 'ML Engineer',
   '• Utilize HOYA’s large-scale production data to develop AI models for manufacturing applications. • Develop Machine Learning and Deep Learning models for quality prediction and machine maintenance forecasting. • Apply computer vision and image processing technologies to optimize production processes and detect incorrect operator actions. • Develop AI models to support production decision-making, such as machine stop.', 'Python, TensorFlow, Kubernetes',
   'Experienced (non-manager)', 'Ho Chi Minh City', NULL, DATE '2026-08-08', DATE '2026-06-29', false, 24000000, 34000000,
   'VND', false),
  ('vietnamworks', 'vnw-eval-016', 'https://www.vietnamworks.com/machine-vision-engineer-ky-su-thi-giac-may-2061678-jv', 'Machine Vision Engineer (Kỹ Sư Thị Giác Máy)', 'Công Ty TNHH Standard Units Supply Việt Nam', 'ML Engineer',
   'Trách nhiệm chính • Thiết kế và phát triển các giải pháp Machine Vision phục vụ: - Kiểm tra chất lượng sản phẩm - Đo lường kích thước, hình dạng - Nhận dạng mã vạch, QR Code, OCR - Robot Guidance • Lựa chọn và cấu hình camera, ống kính, đèn, và các thiết bị ngoại vi liên quan. Phát.', 'Python, scikit-learn, MLflow',
   'Experienced (non-manager)', 'Da Nang', NULL, DATE '2026-08-09', DATE '2026-07-01', false, 1500, 2500,
   'USD', false),
  ('vietnamworks', 'vnw-eval-017', 'https://www.vietnamworks.com/computer-vision-engineer-factory-automation-2061537-jv', 'Computer Vision Engineer (Factory Automation)', 'Vietnamworks'' Client', 'ML Engineer',
   'You will play a critical role in evaluating, implementing, and supporting AI-powered visual inspection solutions for manufacturing customers. This position combines technical expertise in machine vision, image processing, and AI with direct customer engagement to deliver high-performance inspection systems across diverse industries. Working closely with sales teams in Vietnam, engineering teams in Japan, and Technical.', 'Java, Spark, Hadoop',
   'Experienced (non-manager)', 'Ho Chi Minh City', NULL, NULL, DATE '2026-07-02', false, NULL, NULL,
   NULL, false),
  ('vietnamworks', 'vnw-eval-018', 'https://www.vietnamworks.com/data-analyst-2074930-jv', 'Data Analyst', 'Home Credit Vietnam - Explore Your Dream Team', 'Data Analyst',
   'Theo quy định pháp luật hiện hành về bảo vệ dữ liệu cá nhân, bao gồm Luật Bảo vệ dữ liệu cá nhân và các văn bản hướng dẫn thi hành, Công ty Tài chính TNHH MTV Home Credit Việt Nam (“Home Credit”) thực hiện việc thu thập và xử lý dữ liệu cá.', 'SQL, Excel, Power BI',
   'Intern/Student', 'Hanoi', NULL, DATE '2026-08-11', DATE '2026-07-10', true, 7000000, 10000000,
   'VND', false),
  ('vietnamworks', 'vnw-eval-019', 'https://www.vietnamworks.com/data-analyst-after-sales-parts-business-2064342-jv', 'Data Analyst (After Sales Parts Business)', 'Công Ty TNHH Ô Tô Isuzu Việt Nam', 'Data Analyst',
   'We are looking for a Data Analyst to support the Parts Business team in driving data-driven decision making. This role is responsible for managing business data, analyzing market and dealer insights, monitoring competitor activities, and developing reports and dashboards: - Build, maintain, and update databases to ensure data accuracy, quality, and availability for parts business.', 'SQL, Tableau, Excel',
   'Fresher/Entry level', 'Ho Chi Minh City', NULL, DATE '2026-08-12', DATE '2026-07-03', false, NULL, NULL,
   NULL, true),
  ('vietnamworks', 'vnw-eval-020', 'https://www.vietnamworks.com/senior-data-analyst-2074081-jv', 'Senior Data Analyst', 'Bosch Global Software Technologies Company Limited', 'Data Analyst',
   '• Responsible for PBI (Power BI) development activity • Extract Data from sources • Transform raw data into usable data • Modelling data which follows data science theory • Load data to PBI, then perform Visualization regarding to customer request • Responsible for PBI operation activity • Answer customer concerns • Consult for customer concern or requests • Perform bug/issue fixing • Apply.', 'SQL, Power BI, Excel',
   'Intern/Student', 'Da Nang', NULL, DATE '2026-08-13', DATE '2026-07-04', true, 9000000, 13000000,
   'VND', false),
  ('vietnamworks', 'vnw-eval-021', 'https://www.vietnamworks.com/senior-data-analyst--2039989-jv', 'Senior Data Analyst', 'Công Ty Cổ Phần Chứng Khoán SSI', 'Data Analyst',
   '1. Phân tích & trực quan hóa dữ liệu: - Thu thập, xử lý, và phân tích dữ liệu từ nhiều nguồn khác nhau để hỗ trợ ra quyết định kinh doanh. - Xây dựng các báo cáo, dashboard trực quan hóa dữ liệu để hỗ trợ hoạt động kinh doanh/vận hành. - Theo dõi và đánh.', 'SQL, Looker, Excel',
   'Experienced (non-manager)', 'Hanoi', NULL, DATE '2026-08-14', DATE '2026-07-05', false, NULL, NULL,
   NULL, false),
  ('vietnamworks', 'vnw-eval-022', 'https://www.vietnamworks.com/business-intelligence-specialist-senior-2044474-jv', 'Business Intelligence Specialist (Senior)', 'NEYU', 'Other',
   'ABOUT THIS POSITION The Business Intelligence Specialist (Senior) focuses on bridging the gap between raw data and executive execution. You will lead a specialized team to build the company’s data infrastructure, ensuring that every department, from Marketing to Commercial, operates from a Single Source of Truth. Your mission is to move the organization beyond "viewing".', 'SQL, Excel',
   'Manager', 'Ho Chi Minh City', NULL, DATE '2026-08-20', DATE '2026-07-08', false, 15000000, 20000000,
   'VND', false);
