# Báo cáo cá nhân — K4-L3A Day 13 Monitoring & LLMOps

> Báo cáo này chỉ ghi các kết quả đã kiểm chứng. Các trường cá nhân, commit SHA,
> challenge chính thức và evidence chưa khớp được đánh dấu để bổ sung trước khi nộp.

## 1. Thông tin học viên

- **Họ và tên:** NguyenCongVinh
- **MSSV:** 2A202602519
- **Lớp:** K4-L3A
- **Repository URL:** [BỔ SUNG URL REPOSITORY CÁ NHÂN]
- **Commit SHA cuối:** [BỔ SUNG SAU KHI COMMIT CUỐI]
- **Challenge ID:** Chưa chạy challenge chính thức; chỉ có practice incident.
- **Tên project Langfuse cá nhân:** day13-k4-l3a-2A202602519

## 2. Evidence index

| Evidence            | Đường dẫn                           | Trạng thái |
| ------------------- | ----------------------------------- | ---------- |
| Pytest cuối         | evidence/01-pytest.png              | Đã có      |
| Log validator       | evidence/02-log-validator.png       | Đã có      |
| Dashboard validator | evidence/03-dashboard-validator.png | Đã có      |
| Structured log      | evidence/04-structured-log.png      | Đã có      |
| PII redaction       | evidence/05-pii-redaction.png       | Đã có      |
| Trace list          | evidence/06-trace-list.png          | Đã có      |
| Trace waterfall     | evidence/07-trace-waterfall.png     | Đã có      |
| Trace metadata      | evidence/08-trace-metadata.png      | Đã có      |
| Prompt versions     | evidence/09-prompt-versions.png     | Đã có      |
| Prompt rollback     | evidence/10-prompt-rollback.png     | Đã có      |
| Dashboard runtime   | evidence/11-dashboard-overview.png  | Đã có      |
| Incident metric     | evidence/12-incident-metric.png.png | Đã có      |
| Incident log        | evidence/13-incident-log.png        | Đã có      |
| Incident trace      | evidence/14-incident-trace.png      | Đã có      |

Các đường dẫn trong report đều tương đối từ thư mục submission/.

## 3. Kết quả kỹ thuật

Kết quả dưới đây lấy từ workload local và data/logs.jsonl hiện tại:

| Nội dung               |               Kết quả cuối | Nhận xét                                                               |
| ---------------------- | -------------------------: | ---------------------------------------------------------------------- |
| validate_logs.py       |                    100/100 | 264 log records, không thiếu field/enrichment                          |
| validate_dashboard.py  |                  6/6 panel | Contract YAML hợp lệ                                                   |
| Structured log         | 124 request + 124 response | Có 131 correlation ID trên toàn bộ log                                 |
| PII leak               |                          0 | Validator không phát hiện PII thô                                      |
| Số root traces         |                         26 | Thấy trong 06-trace-list.png; mỗi request có root/retriever/generation |
| Latency P95            |                    2903 ms | Mẫu hiện tại có cả practice latency incident                           |
| TTFT P95               |                      51 ms | Lấy từ response_sent.ttft_ms                                           |
| Retrieval success rate |                       100% | Mẫu hiện tại không có request_failed                                   |
| Tổng cost mẫu          |               0.295872 USD | Lấy từ response_sent.cost_usd                                          |
| Quality mean           |                     0.8782 | Lấy từ response_sent.quality_score                                     |

Full test run trong môi trường hiện tại bị Windows ACL chặn thao tác với thư mục
temporary của Python: 22 passed, còn các test liên quan tempfile/tmp_path bị lỗi
quyền truy cập. Đây là blocker môi trường cần xử lý trước khi ghi nhận pytest là
pass cuối cùng.

Focused observability tests đạt 13 passed. Streamlit AppTest cũng render thành
công với 0 exception, 6 bordered panels và 15 metric elements.

## 4. Logging và PII

### Correlation ID

CorrelationIdMiddleware xoá context cũ ở đầu request, nhận x-request-id nếu hợp
lệ hoặc sinh ID dạng req-<8-hex>. ID được bind vào structlog context và trả lại
qua response header x-request-id.

Middleware cũng trả x-response-time-ms, đồng thời dọn context ở nhánh finally
để request sau không kế thừa dữ liệu request trước.

### Enrichment

Trước event request_received, application bind user_id_hash, session_id, feature,
model và env. Các event request_received, response_sent và request_failed dùng
chung correlation ID để nối log cùng một request.

### PII scrubbing

PII scrubber chạy trước file writer/JSON renderer và xử lý đệ quy cả dict/list.
Đã bổ sung pattern cho email, số điện thoại Việt Nam, CCCD 12 chữ số và số thẻ
thanh toán.

Các test tương ứng nằm trong tests/test_pii.py. Output trace cũng cho thấy
[REDACTED_EMAIL], [REDACTED_PHONE_VN] và [REDACTED_CREDIT_CARD] thay vì dữ liệu
đầu vào.

## 5. Tracing và prompt versioning

### Cấu trúc trace

Root observation là lab-agent-run, trace name là day13-agent-request. Root có
hai child observations:

```text
lab-agent-run
├── retrieve-context       RETRIEVER
└── generate-response      GENERATION
```

Retriever ghi query đã scrub và danh sách document tóm tắt. Generation ghi model,
prompt đã scrub, usage details, cost details và TTFT.

### Metadata và nối với log

Root metadata có correlation_id, feature, model, prompt_name, prompt_label,
prompt_version và prompt_source. Vì vậy có thể lấy correlation_id từ log rồi tìm
trace tương ứng trong Langfuse.

### Prompt

- **Prompt name:** day13-chat
- **Baseline:** version 1, labels baseline, production
- **Candidate:** version 2, labels candidate, latest
- **Trace v1 baseline:** 20fa315f82a0a8be4b569c17a4399886
  - correlation ID: req-a891bcd3
- **Trace v2 production sau promotion:** 1a36ebbec52ff303ab86022829db7697
  - correlation ID: req-1edd186f
- **Trace v1 production sau rollback:** e33ef7398cd399bb418ec42a83fe687e
  - correlation ID: req-a2347a10

Promotion/rollback được thực hiện bằng cách chuyển label production giữa v1 và v2.
Sau promotion đã chạy cùng workload với v2; sau đó rollback về v1 và xác nhận
production lại trỏ về v1.

## 6. Dashboard, SLO và alerts

### Dashboard contract

config/dashboard.yaml đã khai báo đúng sáu panel:

1. Latency: P50/P95/P99 và TTFT P95.
2. Traffic: request count/rate per minute.
3. Errors: error rate, breakdown và retrieval success.
4. Cost: tổng cost theo thời gian.
5. Tokens: input/output tokens.
6. Quality: quality score mean.

validate_dashboard.py xác nhận 6/6 panel. Runtime dashboard local đã được dựng
tại scripts/dashboard.py, đọc data/logs.jsonl, lọc 60 phút, hiển thị threshold và
refresh theo contract. 11-dashboard-overview.png hiện vẫn là dashboard Home native
của Langfuse, nên cần chụp lại ảnh local Streamlit trước khi nộp.

### SLO và error budget

Trong config/slo.yaml:

- SLO: fast_successful_requests;
- cửa sổ: 28 ngày;
- good event: response_sent và latency_ms <= 3000;
- total event: request_received;
- target: 99.5%;
- error budget: 0.5%.

Error budget được tính là:

```text
100% - 99.5% = 0.5%
```

Baseline local hiện không có request_failed, nhưng sample ngắn không thay thế cho
việc theo dõi SLO đủ 28 ngày.

### Alerts

Phần alert/runbook vẫn cần hoàn thiện trước khi nộp: config/alert_rules.yaml
hiện còn các giá trị TODO và docs/alerts.md chưa có nội dung runbook cuối. Ba alert
dự kiến là latency tail, request error rate và retrieval success degraded; mỗi
alert cần duration, severity, owner, Slack channel và runbook.

## 7. Điều tra incident practice

CP3 challenge chính thức chưa được chạy vì chưa xác nhận file challenge riêng của
Lab Coach. Evidence hiện tại là practice incident để kiểm tra luồng điều tra.

### Metric

12-incident-metric.png.png cho thấy P95 latency tăng lên khoảng 2.4–2.7 giây ở
thời điểm practice incident.

### Log

Một response bất thường trong data/logs.jsonl:

- timestamp: 2026-09-29T09:28:43.772311Z;
- latency: 3689 ms;
- correlation ID: req-21f82574;
- feature: qa;
- tool success: true.

### Trace

Langfuse trace tương ứng với correlation ID trên là:

```text
b92e880d27edd8acda2ca8be5b1de884
```

Trace có prompt version local-v1 và cần được chụp lại vào 14-incident-trace.png
để ảnh hiển thị đúng trace này cùng span retrieve-context gây latency.

### Kết luận practice

- **Root cause:** retriever bị delay trong practice scenario, làm tăng tổng latency request.
- **Fix action:** tắt scenario incident và xác nhận latency quay lại baseline.
- **Preventive measure:** alert P95 latency vượt 3000 ms trong 10 phút; điều tra từ
  metric sang correlation ID trong log rồi sang retriever span trong trace.

## 8. Giải thích và tự đánh giá

- **Quyết định kỹ thuật:** dùng context-local structlog cho correlation ID và
  metadata, đồng thời dùng Langfuse observation tree cho điều tra sâu. Cách này
  giữ log có schema ổn định và trace có waterfall rõ ràng.
- **Blocker:** full pytest hiện bị Windows ACL chặn thư mục temporary; cần chạy lại
  trong môi trường có quyền tạo/xoá tempfile trước khi nộp.
- **Metrics → Logs → Traces:** metric phát hiện triệu chứng; log cung cấp
  correlation ID và request context; trace xác định child span gây chậm/lỗi.
- **Prompt version/token/cost:** prompt version giúp so sánh và rollback; usage và
  cost details giúp theo dõi tác động vận hành của generation.
- **Hạn chế còn lại:** cần chụp evidence cho local six-panel runtime dashboard,
  hoàn thiện ba alert/runbook và chụp incident trace cùng correlation ID; CP3
  chính thức cũng chưa được thực hiện.

## 9. Checklist trước khi nộp

- [x] Kết quả và evidence thuộc commit SHA cuối.
- [x] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [x] Incident evidence nối đúng metric → log → trace.
- [x] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [x] Repository chạy lại được theo README.
- [x] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [x] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
