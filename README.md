# N44_2026_LTM_018_002_006

Đồ án cuối kỳ môn **Lập trình mạng** — mô phỏng điều phối đàn drone trình diễn ánh sáng bằng C11/POSIX sockets, TCP, UDP multicast, `epoll` và đồng bộ đồng hồ Cristian.

**GVHD:** TS. Nguyễn Văn Hiếu · **Lớp:** 23KTMT1 · **Khoa:** Điện tử và Trí tuệ nhân tạo, Trường Đại học Bách khoa – Đại học Đà Nẵng.

| Thành viên | MSSV | Đóng góp |
|---|---|---|
| Dương Tấn Lĩnh | 106230018 | 33,3 % |
| Nguyễn Công Bình | 106230002 | 33,3 % |
| Nguyễn Tấn Dũng | 106230006 | 33,3 % |

## Báo cáo và phụ lục

- [Báo cáo tổng hợp PDF](docs/BAO_CAO_DRONE_LIGHT_SHOW.pdf)
- [Bản Word](docs/BAO_CAO_DRONE_LIGHT_SHOW.docx)
- [Giao thức và giới hạn triển khai](docs/IMPLEMENTATION.md)
- [Số liệu và ảnh minh chứng](evidence/README.md)

## Cấu trúc

```text
src/common/    Giao thức DLSP, TCP stream, kiểm tra tham số, geofence
src/server/    GCS đề xuất và baseline server
src/agent/     Agent đề xuất, baseline agent và failsafe
scripts/       Sinh kịch bản, đo đạc, vẽ hình, bài bay SITL
tests/        Kiểm thử C và Python
docs/         Báo cáo PDF/Word và tài liệu kỹ thuật
 evidence/     Số liệu gốc, ảnh, biểu đồ và ULog chuyến bay
 tools/        Sinh báo cáo và xuất PDF
 data/         Kịch bản nhị phân mẫu
```

## Biên dịch và kiểm thử

Yêu cầu **Linux** (có `epoll`, `timerfd`), GCC, GNU Make và Python **3.10+**. Phần mạng và `make test` chỉ dùng thư viện chuẩn.

```bash
make
make test
```

Các test chạy socket thật trên localhost, không chạy PX4. Kiểm thử bổ sung MAVLink/PX4 dùng mock và gói UDP tự sinh:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
make test-sitl PX4_PYTHON=.venv/bin/python
```

## Chạy mô phỏng mạng

Terminal 1:

```bash
python3 -I scripts/generate_show.py --drones 5 --shape heart --output show.bin
./bin/gcs_server --show show.bin --lead-ms 1500
```

Terminal 2:

```bash
for i in $(seq 0 4); do
  ./bin/drone_agent --id "$i" --show-ms 3000 &
done
wait
```

Mọi agent phải có ID khác nhau và khớp số drone trong `show.bin`. Đổi **cả số lượng sinh show và vòng lặp** thành 100 để thử quy mô 100 tiến trình. Dừng GCS bằng Ctrl+C sau khi agent hoàn tất. Mặc định GCS dùng TCP `127.0.0.1:8080`, đồng bộ UDP `127.0.0.1:9091`, multicast `239.255.0.1:9090` trên loopback; `--port`, `--sync-port`, `--multicast` của server và agent phải khớp.

Đối chứng baseline (hai terminal riêng):

```bash
./bin/baseline_server --show show.bin --rate 10 --duration 3
```

```bash
for i in $(seq 0 4); do
  ./bin/baseline_agent --id "$i" --loss 10 &
done
wait
```

`--loss` và `--jitter-ms` mô phỏng suy giảm ở tầng ứng dụng. Baseline vẫn dùng TCP; đây không phải mất gói TCP trên đường truyền hay phép thử `tc netem`.

## Tái lập đánh giá

```bash
python3 -I scripts/evaluate_baseline.py --quick
# Toàn bộ TN-1…TN-5 (khoảng 10–15 phút):
python3 -I scripts/evaluate_baseline.py
```

Chạy nhanh ghi `evidence/results_quick.json`; chạy đầy đủ ghi đè `evidence/results.json`. Số liệu trong báo cáo được đo ngày **16/11/2026**, trước đợt chỉnh lý mã nguồn; chạy lại trên phiên bản/máy khác sẽ cho số đo thời gian và CPU khác. Xem [evidence/README.md](evidence/README.md) về cách đọc các kết quả.

## Demo PX4 SITL độc lập

Demo chỉ điều khiển **một drone SITL**, chưa nối trực tiếp agent C với PX4. Cần PX4 v1.14.4 ở `~/PX4-Autopilot`, jMAVSim và QGroundControl 4.4.5; các phần mềm này cài riêng.

Trong terminal tương tác:

```bash
cd ~/PX4-Autopilot
PX4_SIM_SPEED_FACTOR=1 make px4_sitl_default jmavsim
```

Từ thư mục dự án, với Python đã cài `requirements.txt`:

```bash
.venv/bin/python -I scripts/sitl_flight.py
.venv/bin/python -I scripts/sitl_flight.py --execute-sitl
```

Lệnh đầu chỉ xem trước. Lệnh có `--execute-sitl` xác minh tiến trình PX4 cục bộ và heartbeat, gửi OFFBOARD/ARM, bay 4 điểm mốc rồi gửi LAND. Giữ QGroundControl mở để xác nhận đã hạ cánh/disarm. Không dùng cho thiết bị thật. Không chuyển console PX4 vào file log vì có thể làm đầy ổ đĩa.


## Phạm vi đã hoàn thành

- GCS/agent C, nạp một điểm mốc cho mỗi drone, đồng bộ bốn timestamp, multicast trigger, heartbeat và failsafe mô phỏng.
- Baseline streaming 10 Hz; khung thực nghiệm quy mô 2–100 agent và các điều kiện mạng giả lập.
- Demo bay một PX4 SITL riêng, ảnh UI và log chuyến bay.

Chưa có cầu nối MAVLink từ agent C tới PX4, visualizer 100 drone, tích hợp trình phát spline nhiều điểm vào agent mạng, tránh va chạm hoặc xác thực mật mã. Callback failsafe tạo cấu trúc lệnh mô phỏng và log, chưa truyền lệnh bay thật. Không diễn giải 100 agent localhost là 100 mô phỏng động lực học PX4.

## Mô-đun spline và sinh đội hình

`src/common/spline.*` nội suy Cubic Hermite 3D, khớp vị trí và vận tốc tại hai đầu đoạn. `tools/pattern_generator.py` sinh đội hình ngôi sao → xoắn ốc, kiểm tra tốc độ, geofence và khoảng cách lấy mẫu trước khi ghi tệp. Mô-đun này có test riêng trong `make test`, chưa nối vào vòng phát quỹ đạo của GCS/agent.

```bash
python3 -I tools/pattern_generator.py --drones 20 --output show_waypoints.bin --json show_waypoints.json
```

Định dạng đầu ra là chuỗi khung DLSP type `0x0A`, khác tệp `SHOW` một điểm mốc của `generate_show.py`; chưa thể truyền tệp này vào `gcs_server --show`.
