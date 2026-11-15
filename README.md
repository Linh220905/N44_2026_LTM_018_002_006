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

**Giới hạn hiện tại:** Demo PX4 chưa nối GCS/agent; chưa triển khai baseline unicast, đồng bộ Cristian, benchmark và phép so sánh hiệu năng. Không dùng ảnh bay đơn lẻ làm bằng chứng cải thiện thuật toán. Chỉ số rớt sequence MAVLink phía nhận không tự chứng minh mất gói mạng.
