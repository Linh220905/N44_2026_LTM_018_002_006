# Thiết kế và phạm vi triển khai

## Luồng chạy

1. GCS đọc tệp `SHOW`, nhận `HELLO_REQ` qua TCP/epoll và gửi ACK + một điểm mốc cho từng ID.
2. Agent đo K mẫu UDP unicast với time server, lấy offset của mẫu RTT nhỏ nhất.
3. Khi GCS gửi xong dữ liệu cho đủ N kết nối, GCS ấn định `T_target` và phát trigger multicast lặp ở 4 Hz.
4. Agent đặt `timerfd` tuyệt đối theo đồng hồ đã bù offset. `poll` nhận cả timer và multicast để tiếp tục xử lý heartbeat/STOP khi chờ. Hết timer, agent ghi timestamp bắt đầu.
5. `--show-ms` bật giai đoạn giám sát sau khởi động; không có cờ này agent chỉ kiểm chứng đồng bộ khởi động rồi thoát. Timeout heartbeat thực tế của agent là 2 s; bộ failsafe có mặc định 1,5 s và được agent cấu hình lại.

Tất cả socket của bản mô phỏng dùng loopback. Khi nạp xong dữ liệu, `ready_count` mới thể hiện GCS gửi xong TCP, **chưa phải** ACK đồng bộ hoàn tất từ agent. Nếu đồng bộ quá chậm, agent từ chối trigger đã quá hạn; giao thức hiện chưa có READY barrier hoặc tái lập lịch tự động.

## DLSP

Header 16 byte, big-endian: magic `0x5058` (2), version (1), type (1), sequence (4), payload length (4), CRC (2), reserved (2). CRC-16/CCITT-FALSE tính trên toàn khung với hai byte checksum bằng 0. CRC phát hiện lỗi, không xác thực người gửi.

| Type | Tên | Kênh / nội dung |
|---|---|---|
| 0x01 / 0x02 | HELLO_REQ / HELLO_ACK | TCP, ID 2 byte |
| 0x03 | TRAJECTORY_DATA | TCP, ID + số điểm + bản ghi; agent hiện chấp nhận 1 điểm |
| 0x04 / 0x05 | TIME_SYNC_REQ / TIME_SYNC_RESP | UDP unicast, T1 / T1,T2,T3 (µs u64) |
| 0x06 | SWARM_HEARTBEAT | Multicast, không payload |
| 0x07 | SHOW_ARM_TRIGGER | Multicast, `T_target` (µs u64) |
| 0x08 | EMERGENCY_STOP | Multicast cho agent đề xuất / TCP cho baseline |
| 0x09 | SETPOINT | TCP baseline, payload 25 byte |
| 0x0A | SHOW_WAYPOINT_DATA | Phần mở rộng spline, chưa nối vào GCS/agent |

`src/common/stream.c` gửi đủ byte và ghép khung theo độ dài; không giả định một lần `recv` tương ứng một frame. GCS và baseline có buffer HELLO riêng cho từng kết nối. Các datagram dài hơn buffer bị từ chối, không giải mã khung đã bị cắt.

## Hai định dạng tệp kịch bản

- `scripts/generate_show.py`: magic `SHOW`, số drone u16, mỗi drone một bản ghi 25 byte `(id u16, t_ms u32, x y z yaw f32, r g b u8)`. Đây là định dạng hai server đang đọc. Cao độ lưu dương, agent đổi dấu z khi kiểm tra geofence NED.
- `tools/pattern_generator.py`: nối các frame DLSP type 0x0A; mỗi payload có ID u16, số mốc u16, mốc 31 byte `(t_ms u32, x y z vx vy vz f32, r g b u8)`, tọa độ NED. Thư viện `spline.*` nội suy Hermite. Hai thành phần này có test riêng, chưa tích hợp phát show qua mạng.

## Cách đo và giới hạn kết luận

- Baseline dùng TCP unicast 10 Hz. Agent bỏ điểm đặt sau khi nhận để giả lập mất gói ở ứng dụng, không đo mất gói TCP thật.
- Hệ đề xuất giả lập lệch đồng hồ ±50 ms và trễ hàng đợi một chiều bằng phân phối mũ. Đồng hồ các tiến trình trên cùng host có nền chung, nên đây là mô hình đồng hồ phân tán giả lập.
- Băng thông đếm byte DLSP do server gửi, không tính header TCP/IP, retransmission, ACK và telemetry. Chuẩn bị nạp dữ liệu cũng không tính vào băng thông pha trình diễn.
- Sai số đề xuất trong phép thử mất gói là mô hình `v * sai số đồng bộ`; chưa là vị trí đo từ PX4. Baseline đo giữ điểm đặt cũ so với điểm đặt mới.
- GCS/agent giới hạn 100 drone, một điểm mốc/agent. Bài bay MAVLink là một drone SITL độc lập. Chưa có bridge agent C → PX4, visualizer đàn hoặc kiểm chứng tránh va chạm thực tế.
- Failsafe hiện tạo cấu trúc lệnh và callback/log mô phỏng. Các enum AUTO_HOVER nội bộ không phải ánh xạ mode PX4 hoàn chỉnh.

Các số liệu đã xuất trong báo cáo được đo ngày 16/11/2026. Đợt chỉnh lý 18/11/2026 thay cấu trúc thư mục, dùng chung xử lý stream/CLI, bổ sung kiểm tra biên và `timerfd`; không thay số liệu lịch sử thành kết quả mới. Kết quả chạy lại phải được lưu và đối chiếu riêng.
