# PX4 SITL Swarm Coordination

Đồ án mô phỏng điều phối đàn drone: GCS C dùng TCP/epoll để nạp điểm quỹ đạo, các agent nhận heartbeat và lệnh khởi động qua UDP multicast. Có demo bay độc lập trên PX4 SITL/jMAVSim bằng MAVLink và xem telemetry trong QGroundControl.

## Thử phần mạng

```bash
make test
python3 -I scripts/generate_show.py --drones 100 --shape heart --output show.bin
./bin/gcs_server --show show.bin
# Terminal khác: ./bin/drone_agent --id 0
```

`make test` dùng Python có `pymavlink` tại `~/px4-venv/bin/python`; có thể đổi biến `PX4_PYTHON` cho môi trường khác.

## Bay thử PX4 SITL

Cài và build PX4 v1.14.4 riêng tại `~/PX4-Autopilot`. Chạy trong terminal đồ họa:

```bash
cd ~/PX4-Autopilot
PATH="$HOME/px4-venv/bin:$HOME/.local/bin:$PATH" PX4_SIM_SPEED_FACTOR=1 make px4_sitl_default jmavsim
```

Sau khi QGroundControl nhận PX4, từ thư mục dự án chạy:

```bash
~/px4-venv/bin/python -I scripts/sitl_flight.py             # chỉ xem trước
~/px4-venv/bin/python -I scripts/sitl_flight.py --execute-sitl # chỉ chạy SITL, tự gửi LAND
```

## Module An toàn Failsafe & 3D Geofence (Agent 2)

Hệ thống giám sát an toàn cấp thiết bị bay (drone-level failsafe):
- **3D Geofence (`common/geofence.h`, `common/geofence.c`)**: Kiểm tra không gian bay 3D an toàn theo hệ tọa độ NED (North-East-Down: $z < 0$ là độ cao).
- **Failsafe Monitor (`agent/failsafe.h`, `agent/failsafe.c`)**:
  - Tự động phát hiện mất nhịp Heartbeat GCS quá 1.5s $\rightarrow$ chuyển chế độ `AUTO_HOVER` (`MAV_CMD_DO_SET_MODE`).
  - Vi phạm hàng rào Geofence hoặc điện áp pin $< 10\%$ $\rightarrow$ tự động kích hoạt hạ cánh khẩn cấp `MAV_CMD_NAV_LAND`.
  - Hỗ trợ lệnh ngắt khẩn cấp thủ công từ GCS (`FAILSAFE_EMERGENCY_TRIGGER`).
- **Unit Test (`tests/test_failsafe.c`)**:
  - Chạy kiểm thử: `make bin/test_failsafe && ./bin/test_failsafe`

## Đánh giá Hệ tham chiếu Baseline vs Kiến trúc đề xuất

Hệ thống cung cấp cả hai mô hình kiến trúc để đối chứng trực tiếp:
- **Kiến trúc đề xuất (Pre-load + Multicast Trigger):** `bin/gcs_server` và `bin/drone_agent`.
- **Hệ tham chiếu Baseline (Unicast Real-time Streaming):** `bin/baseline_server` và `bin/baseline_agent`.

Chạy toàn bộ bộ đánh giá thực nghiệm (Scale $N=2..100$, mất gói $p_{loss}=0\%..20\%$, biểu đồ so sánh):

```bash
/home/linh/miniconda3/bin/python scripts/evaluate_baseline.py
# Biên dịch lại báo cáo Word:
/home/linh/miniconda3/bin/python tools/build_report.py
```

**Giới hạn hiện tại:** Demo PX4 chưa nối trực tiếp MAVLink bridge đàn đa drone (chạy demo độc lập 1 drone SITL); chưa dùng Linux tc netem trên giao diện vật lý ngoài localhost.
