# Minh chứng và dữ liệu thực nghiệm

- `results.json`: số liệu dùng cho TN-1…TN-5 và các mẫu đo; đo ngày 16/11/2026 trước đợt chỉnh lý mã nguồn. `meta.date` là mốc chạy ban đầu; TN-3 được chạy lại cùng ngày để tổng hợp RMS đúng theo toàn đàn.
- `frames.json`: bốn khung DLSP bắt bằng socket UDP/multicast thật; có hex, CRC và header giải mã. Đây không phải PCAP hoặc ảnh Wireshark.
- `hinh_*.png`, `diagrams/`: biểu đồ và sơ đồ trong báo cáo. Biểu đồ kết quả lấy từ `results.json`; lưu đồ và sơ đồ là hình thiết kế.
- `run_make_test.txt`, `run_swarm4.txt`: output lần chạy minh chứng ngày 16/11; ảnh `hinh_make_test.png`, `hinh_run_swarm4.png` dựng lại chữ từ các tệp này, không phải screenshot terminal trực tiếp.
- `jmavsim_live.png`, `qgroundcontrol_live.png`, `qgc_current.png`, `screen_live_full.png`: ảnh giao diện mô phỏng có sẵn của dự án.
- `hinh11_uorb_listener.png`: kết quả listener được trình bày thành hình; `hinh18_px4_listener_telemetry_status.png` là ảnh minh chứng bổ sung. Các ảnh đơn lẻ không thay thế phép đo định lượng.
- `flight/02_36_09.ulg.gz`: log chuyến bay PX4 SITL gốc, nén gzip; phân tích bằng pyulog, không phải Flight Review trực tuyến.

Tái lập phân tích chuyến bay (không khởi động PX4):

```bash
python3 -I scripts/plot_ulog.py
# Hoặc truyền một log ULog khác (.ulg hoặc .ulg.gz):
python3 -I scripts/plot_ulog.py /path/to/flight.ulg
```

Cần `requirements-report.txt`. Tệp gzip được đọc trực tiếp, không cần giải nén ra repo.

Tạo lại biểu đồ từ dữ liệu đã nộp:

```bash
python3 -I scripts/plot_results.py
```

Các lệnh `evaluate_baseline.py` (không cờ `--quick`), `capture_frames.py` và `plot_ulog.py` ghi đè đầu ra cùng tên. Để bảo toàn bộ số liệu nộp bài, thử trên bản clone riêng hoặc kiểm tra `git diff` trước khi commit kết quả mới.
