#!/usr/bin/env python3
"""Build BAO_CAO_DRONE_LIGHT_SHOW.docx (python3 -I tools/build_report.py).

Every number in the evaluation tables is read from evidence/results.json and
evidence/frames.json, produced by scripts/evaluate_baseline.py and scripts/capture_frames.py.
PX4 flight statistics come from scripts/plot_ulog.py (ULog 02_36_09.ulg).
"""
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from docx.enum.text import WD_ALIGN_PARAGRAPH as AL  # noqa: E402
from docx.shared import Cm, Pt  # noqa: E402

from report_kit import Report  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "evidence"
DG = EV / "diagrams"
OUT = ROOT / "docs" / "BAO_CAO_DRONE_LIGHT_SHOW.docx"
R = json.loads((EV / "results.json").read_text())
FR = json.loads((EV / "frames.json").read_text())
C, L, J = AL.CENTER, AL.LEFT, AL.JUSTIFY

rep = Report("Lập trình mạng – Báo cáo cuối kỳ", "Mô phỏng đàn drone trình diễn ánh sáng")
P, H, B, T, F, EQ, ALG = rep.para, rep.heading, rep.bullets, rep.table, rep.figure, rep.equation, rep.algorithm


def f(x, d=2):
    return f"{x:,.{d}f}".replace(",", " ").replace(".", ",")


def ms(stat, d=2):
    return f"{f(stat['mean'], d)} ± {f(stat['sd'], d)}"


# ============================================================ COVER
MEMBERS = [("Dương Tấn Lĩnh", "106230018"), ("Nguyễn Công Bình", "106230002"), ("Nguyễn Tấn Dũng", "106230006")]


def cover():
    """Layout of the reference report cover: framed page, two logos, upper-case title block."""
    rep.cover_frame()
    for text, after, underline in [("ĐẠI HỌC ĐÀ NẴNG", 2, False), ("TRƯỜNG ĐẠI HỌC BÁCH KHOA", 2, False),
                                   ("KHOA ĐIỆN TỬ VÀ TRÍ TUỆ NHÂN TẠO", 0, True)]:
        p = P(text, align=C, size=13, bold=True, after=after, spacing=1.15)
        if underline:
            for run in p.runs:
                run.underline = True
    rep.logos([EV / "logo_bk.jpg", EV / "logo_khoa.jpg"], height_cm=3.0)
    P("BÁO CÁO CUỐI KÌ", align=C, size=18, bold=True, after=4, spacing=1.2)
    P("HỌC PHẦN: LẬP TRÌNH MẠNG", align=C, size=16, bold=True, after=30, spacing=1.2)
    P("ĐỀ TÀI:", align=C, size=15, bold=True, after=4, spacing=1.2)
    P("MÔ PHỎNG ĐIỀU PHỐI ĐÀN DRONE\nTRÌNH DIỄN ÁNH SÁNG\nTRÊN NỀN TẢNG PX4 VÀ MAVLINK", align=C, size=17,
      bold=True, after=30, spacing=1.3)
    rows = [("GVHD:", "TS. NGUYỄN VĂN HIẾU")]
    rows += [("SVTH:" if i == 0 else "", f"{name.upper()} - {mssv}") for i, (name, mssv) in enumerate(MEMBERS)]
    rows += [("Lớp:", "23KTMT1")]
    tbl = rep.doc.add_table(rows=len(rows), cols=2)
    for r, (a, b) in enumerate(rows):
        for c, text in enumerate((a, b)):
            cell = tbl.rows[r].cells[c]
            cell.width = Cm(2.8 if c == 0 else 9.0)
            p = cell.paragraphs[0]
            p.paragraph_format.first_line_indent = Cm(0)
            p.paragraph_format.line_spacing = 1.15
            p.paragraph_format.space_before = Pt(6 if r in (1, len(rows) - 1) else 0)
            p.paragraph_format.space_after = Pt(0)
            p.alignment = L
            rep.rich(p, text, size=13, bold=True)
    rep._fix_grid(tbl, [2.8, 9.0])
    tbl.alignment = 1
    P("", after=24)
    P("Đà Nẵng, 11/2026", align=C, size=13, bold=True)
    rep.end_cover()


def front_matter():
    rep.toc("MỤC LỤC", 'TOC \\o "1-3" \\h \\z \\u')
    rep.page_break()
    rep.toc("DANH MỤC HÌNH VẼ", 'TOC \\h \\z \\c "Hình"')
    rep.page_break()
    rep.toc("DANH MỤC BẢNG BIỂU", 'TOC \\h \\z \\c "Bảng"')
    rep.page_break()
    P("DANH MỤC TỪ VIẾT TẮT", align=C, bold=True, size=14, after=12)
    T([("Viết tắt", "Tiếng Anh", "Ý nghĩa"),
       ("CRC", "Cyclic Redundancy Check", "Mã kiểm tra dư vòng"),
       ("DLSP", "Drone Light Show Protocol", "Giao thức tầng ứng dụng do nhóm thiết kế"),
       ("EKF2", "Extended Kalman Filter 2", "Bộ ước lượng trạng thái của PX4"),
       ("FSM", "Finite State Machine", "Máy trạng thái hữu hạn"),
       ("GCS", "Ground Control Station", "Trạm điều khiển mặt đất"),
       ("HB", "Heartbeat", "Bản tin duy trì liên lạc"),
       ("MAVLink", "Micro Air Vehicle Link", "Giao thức bản tin cho phương tiện không người lái"),
       ("NED", "North–East–Down", "Hệ tọa độ địa phương Bắc–Đông–Xuống"),
       ("NTP", "Network Time Protocol", "Giao thức đồng bộ thời gian mạng"),
       ("QGC", "QGroundControl", "Phần mềm trạm mặt đất cho PX4"),
       ("RMS", "Root Mean Square", "Căn bậc hai trung bình bình phương"),
       ("RTT", "Round-Trip Time", "Thời gian khứ hồi"),
       ("SITL", "Software In The Loop", "Mô phỏng phần mềm điều khiển bay trên máy tính"),
       ("TTL", "Time To Live", "Số chặng tối đa của gói IP"),
       ("uORB", "Micro Object Request Broker", "Bus bản tin nội bộ của PX4")],
      widths=[2.4, 5.6, 8.0], header=True)


# ============================================================ 1
def ch1():
    H("1. Phân công công việc", 1)
    T([("Thành viên", "Nhiệm vụ chính", "Sản phẩm bàn giao", "Tỷ lệ"),
       ("Dương Tấn Lĩnh\n106230018", "Thiết kế giao thức DLSP và GCS Server",
        "src/common/protocol.c (đóng gói, giải mã, CRC-16, big-endian); src/server/gcs_server.c (vòng lặp epoll, "
        "Time Server, phát multicast); kiểm thử đơn vị giao thức", "33,3 %"),
       ("Nguyễn Công Bình\n106230002", "Drone Agent, an toàn và tích hợp PX4",
        "src/agent/drone_agent.c (đồng bộ Cristian, kích hoạt theo T_{target}); src/agent/failsafe.c, src/common/geofence.c; "
        "cài đặt PX4 SITL, jMAVSim, QGroundControl; scripts/sitl_flight.py", "33,3 %"),
       ("Nguyễn Tấn Dũng\n106230006", "Hệ tham chiếu, đo đạc và báo cáo",
        "src/server/baseline_server.c, src/agent/baseline_agent.c; scripts/evaluate_baseline.py (ma trận TN-1…TN-5); "
        "xử lý số liệu, vẽ biểu đồ, viết báo cáo", "33,3 %"),
       ("", "", "Tổng cộng", "100 %")],
      "Phân công nhiệm vụ và tỷ lệ đóng góp", widths=[3.2, 3.6, 7.6, 1.6], align=[L, L, L, C])


# ============================================================ 2
def ch2():
    H("2. Đặt vấn đề: tính cấp thiết và ý nghĩa", 1)
    H("2.1. Bối cảnh", 2)
    P("Trình diễn ánh sáng bằng đàn drone là hình thức dùng hàng trăm thiết bị bay mang đèn LED RGB để vẽ hình và chữ "
      "trên bầu trời. Mỗi thiết bị phải có mặt đúng vị trí, bật đúng màu và chuyển động đúng thời điểm thì toàn đàn mới "
      "tạo thành một hình ảnh liền mạch. Một chiếc đi trước hoặc chậm sau vài chục mili-giây đã làm méo hình; lệch xa "
      "hơn có thể làm hai thiết bị bay vào nhau.")
    P("Về bản chất, đây là bài toán **hệ phân tán thời gian thực**: nhiều nút độc lập, mỗi nút có đồng hồ riêng, "
      "chia sẻ chung một kênh vô tuyến, nhưng phải thực hiện cùng một kịch bản với độ đồng bộ cỡ mili-giây. Vì vậy "
      "đề tài nằm đúng trong phạm vi học phần Lập trình mạng: lập trình socket TCP/UDP, truyền nhóm IP multicast, "
      "thiết kế giao thức tầng ứng dụng, ghép kênh vào/ra và đồng bộ đồng hồ qua mạng.")
    H("2.2. Vấn đề thực tế", 2)
    P("Khi điều phối một đàn N thiết bị trên một kênh dùng chung, ba vấn đề mạng xuất hiện cùng lúc:")
    B(["**Băng thông chiều xuống tăng theo N.** Nếu trạm mặt đất gửi điểm đặt vị trí cho từng thiết bị bằng các kết nối "
       "unicast riêng, lưu lượng tỷ lệ với N × tần số × kích thước gói. Kênh Wi-Fi dùng chung sẽ nghẽn khi đàn lớn.",
       "**Đồng hồ các nút không khớp nhau.** Mỗi thiết bị có bộ dao động riêng; nếu không đồng bộ, cùng một lệnh "
       "\"bắt đầu lúc t\" sẽ được thực hiện ở các thời điểm khác nhau. Với vận tốc 2 m/s, lệch 10 ms tương đương "
       "lệch vị trí 2 cm.",
       "**Mất gói và trễ biến thiên.** Trên kênh vô tuyến, gói bị mất hoặc đến muộn là bình thường. Nếu thiết bị "
       "phụ thuộc vào luồng điểm đặt liên tục, mỗi gói mất là một lần thiết bị giữ điểm đặt cũ và tụt lại sau "
       "quỹ đạo thiết kế."])
    H("2.3. Hạn chế của giải pháp hiện tại", 2)
    P("Mô hình phổ biến trong các hệ điều khiển phương tiện trên nền PX4, gồm cả đồ án USV cùng học phần [16], là "
      "một cổng trung gian (gateway) nhận lệnh từ người dùng rồi chuyển thành bản tin MAVLink cho **một** phương tiện "
      "qua UDP. Mô hình này đúng cho một phương tiện nhưng có ba hạn chế khi mở rộng sang đàn:")
    B(["Không giải quyết vấn đề nhất quán thời gian giữa nhiều nút, vì chỉ có một nút.",
       "Chất lượng điều khiển gắn trực tiếp với chất lượng mạng tại từng thời điểm: mạng xấu thì điều khiển xấu.",
       "Đánh giá thường chỉ đo độ trễ và mất gói của chính hệ thống trên localhost, không có hệ đối chứng, nên không "
       "kết luận được cải tiến tốt hơn bao nhiêu."])
    H("2.4. Mục tiêu", 2)
    B(["Thiết kế kiến trúc **tách kênh dữ liệu khỏi kênh thời gian**: quỹ đạo nạp trước qua TCP tin cậy, thời điểm "
       "bắt đầu phát bằng một gói UDP multicast duy nhất, thiết bị tự chạy theo đồng hồ đã đồng bộ.",
       "Đặc tả và hiện thực giao thức nhị phân **DLSP** trên POSIX socket bằng ngôn ngữ C: header 16 byte, số thứ tự, "
       "CRC-16, thứ tự byte mạng.",
       "Hiện thực **đồng bộ đồng hồ Cristian** dạng bốn mốc thời gian, có bộ lọc chọn mẫu RTT nhỏ nhất, và cơ chế "
       "**failsafe** khi mất heartbeat.",
       "Xây dựng **hệ tham chiếu (baseline)** phát điểm đặt unicast thời gian thực và **khung đo tự động** để so sánh "
       "định lượng hai kiến trúc khi thay đổi quy mô đàn, độ trễ và tỷ lệ mất gói.",
       "Tích hợp và kiểm chứng với **PX4 Autopilot SITL** qua MAVLink cho một drone đại diện."], numbered=True)
    H("2.5. Phạm vi", 2)
    P("Toàn bộ thử nghiệm chạy trên một máy Linux, các tiến trình trao đổi qua giao diện loopback. Mỗi drone là một "
      "tiến trình agent độc lập với socket và đồng hồ riêng; tối đa 100 agent. PX4 SITL chạy một phương tiện để kiểm "
      "chứng tầng MAVLink, các drone còn lại không mô phỏng động lực học bay. Điều kiện mạng xấu (trễ, mất gói, lệch "
      "đồng hồ) được giả lập ở tầng ứng dụng như mô tả tại Mục 5.5, không thay đổi cấu hình mạng của máy.")
    H("2.6. Ý nghĩa", 2)
    P("**Về học thuật**, đề tài vận dụng đồng thời các nội dung cốt lõi của học phần: socket hướng kết nối và phi kết "
      "nối, multicast, ghép kênh epoll, tách khung trên dòng byte TCP, mã kiểm tra lỗi, đồng bộ đồng hồ và phát hiện "
      "mất liên lạc. **Về ứng dụng**, mô hình \"nạp trước – kích hoạt đồng loạt\" dùng được cho mọi bài toán nhiều nút "
      "cùng thực hiện một kế hoạch có mốc thời gian: đội drone khảo sát, robot kho vận, mạng cảm biến lấy mẫu đồng bộ.")


# ============================================================ 3
def ch3():
    H("3. Sơ đồ kiến trúc và thiết kế hệ thống", 1)
    H("3.1. Cơ sở công nghệ", 2)
    H("3.1.1. PX4 Autopilot, SITL và QGroundControl", 3)
    P("PX4 là phần mềm điều khiển bay mã nguồn mở [1]. Các module bên trong (ước lượng trạng thái EKF2, điều khiển vị "
      "trí, quản lý chế độ bay, ghi log) trao đổi qua bus bản tin **uORB** theo mô hình publish/subscribe. Ở chế độ "
      "**SITL**, firmware PX4 chạy như một tiến trình trên máy tính, nhận cảm biến giả lập từ bộ mô phỏng jMAVSim và "
      "mở cổng UDP cho MAVLink [2]. Với PX4 v1.14.4, phiên bản SITL thứ i lắng nghe UDP 14580 + i và gửi tới 14540 + i "
      "cho ứng dụng điều khiển ngoài; QGroundControl nhận tại 14550. Mọi chuyến bay được PX4 tự ghi vào tệp nhị phân "
      "ULog (.ulg), đọc được bằng thư viện pyulog [14].")
    H("3.1.2. MAVLink", 3)
    P("MAVLink [3] là giao thức bản tin nhị phân cho phương tiện không người lái. Khung MAVLink v2 có số thứ tự 8 bit, "
      "định danh hệ thống và thành phần, kèm CRC. MAVLink chạy trên UDP nên không bảo đảm thứ tự và không phát lại. "
      "Bảng 2 liệt kê các bản tin nhóm sử dụng.")
    T([("Bản tin", "Hướng", "Vai trò"),
       ("HEARTBEAT", "Hai chiều", "Khai báo sự hiện diện; PX4 chỉ gửi telemetry khi đã nhận heartbeat từ phía ngoài"),
       ("SET_POSITION_TARGET_LOCAL_NED", "Agent → PX4", "Điểm đặt vị trí hệ NED, 10 Hz, bắt buộc trước khi vào OFFBOARD"),
       ("COMMAND_LONG: DO_SET_MODE", "Agent → PX4", "Chuyển chế độ OFFBOARD; failsafe dùng để chuyển AUTO_HOVER"),
       ("COMMAND_LONG: COMPONENT_ARM_DISARM", "Agent → PX4", "Kích hoạt động cơ"),
       ("COMMAND_LONG: NAV_LAND", "Agent → PX4", "Hạ cánh khi kết thúc hoặc khi failsafe"),
       ("LOCAL_POSITION_NED", "PX4 → Agent", "Vị trí ước lượng, dùng đối chiếu với điểm đặt")],
      "Các bản tin MAVLink sử dụng", widths=[5.6, 2.6, 7.8], mono_cols=(0,))
    H("3.1.3. IP Multicast", 3)
    P("IP multicast [6] cho phép một nút gửi **một** bản sao gói tin tới một địa chỉ nhóm lớp D (224.0.0.0/4); mạng "
      "nhân bản gói tới mọi thành viên. Nút nhận gia nhập nhóm bằng tùy chọn socket `IP_ADD_MEMBERSHIP`; nút gửi chọn "
      "giao diện bằng `IP_MULTICAST_IF`. Nhóm dùng địa chỉ 239.255.0.1 thuộc dải phạm vi nội bộ. Hai tính chất quyết "
      "định: chi phí phát một lệnh tới cả đàn không phụ thuộc N, và các thành viên nhận gói gần như cùng lúc.")
    H("3.1.4. Ghép kênh vào/ra với epoll", 3)
    P("Máy chủ phải phục vụ đồng thời tối đa 100 kết nối TCP và một socket UDP. Thay vì tạo một luồng cho mỗi kết nối, "
      "GCS dùng `epoll` [10]: nhân Linux giữ tập socket cần theo dõi và chỉ trả về những socket đã sẵn sàng, nên mỗi "
      "lần gọi `epoll_wait` tốn O(k) với k là số sự kiện, thay vì O(n) như `select`/`poll`. Mọi socket ở chế độ "
      "non-blocking để một agent chậm không chặn các agent khác.")
    H("3.1.5. Đồng bộ đồng hồ Cristian", 3)
    P("Thuật toán Cristian [4] ước lượng độ lệch đồng hồ của máy khách so với máy chủ thời gian bằng một cặp yêu cầu – "
      "trả lời, giả định trễ hai chiều bằng nhau. Nhóm dùng dạng bốn mốc thời gian như NTP [5] để loại thời gian xử lý "
      "tại máy chủ ra khỏi RTT, và lấy nhiều mẫu rồi giữ mẫu có RTT nhỏ nhất (Mục 4.3).")
    H("3.2. Kiến trúc tổng thể", 2)
    P("Hệ thống gồm ba tầng (Hình 1). **Tầng điều phối** là GCS Master Server viết bằng C, một tiến trình, một vòng lặp "
      "epoll. **Tầng thực thi** gồm N tiến trình Drone Agent, mỗi tiến trình là một nút mạng đầy đủ: socket TCP, socket "
      "UDP unicast, socket multicast và đồng hồ riêng. **Tầng mô phỏng** gồm PX4 SITL + jMAVSim + QGroundControl cho "
      "drone đại diện; các drone còn lại dùng mô hình vị trí theo thời gian.")
    F(DG / "h01_kien_truc.png", "Kiến trúc tổng thể ba tầng của hệ thống đề xuất")
    P("Ba kênh truyền được chọn theo đặc tính dữ liệu (Bảng 3):")
    T([("Dữ liệu", "Kênh", "Lý do"),
       ("Bắt tay, quỹ đạo", "TCP :8080", "Cần toàn vẹn tuyệt đối, khối lượng lớn, gửi trước giờ diễn nên không bị ràng "
                                         "buộc thời gian thực; TCP có sẵn phát lại, thứ tự, kiểm soát luồng"),
       ("Mẫu đồng bộ đồng hồ", "UDP unicast :9091", "Cần trễ thấp và ổn định; phát lại của TCP làm sai phép đo RTT; mất "
                                                    "một mẫu không sao vì lấy K mẫu"),
       ("Heartbeat, trigger, dừng khẩn", "UDP multicast 239.255.0.1:9090", "Cần tới cả đàn cùng lúc, chi phí không đổi "
                                                                          "theo N"),
       ("Lệnh bay", "MAVLink/UDP 14580", "Giao diện chuẩn của PX4 SITL")],
      "Lựa chọn kênh truyền theo loại dữ liệu", widths=[3.8, 4.2, 8.0])
    H("3.3. Thành phần và nhiệm vụ", 2)
    T([("Thành phần", "Tệp nguồn", "Nhiệm vụ"),
       ("Protocol Codec", "src/common/protocol.c", "Đóng gói/giải mã khung DLSP, CRC-16/CCITT-FALSE, big-endian, kiểm tra "
                                               "magic, version, type, độ dài"),
       ("Show Loader", "src/server/gcs_server.c", "Đọc tệp show.bin (\"SHOW\" + số drone + bản ghi 25 byte), từ chối tệp sai "
                                               "định dạng trước khi mở socket"),
       ("Session Manager", "src/server/gcs_server.c", "Chấp nhận kết nối TCP, ghép đủ HELLO_REQ, cấp drone_id, gửi HELLO_ACK + "
                                                   "TRAJECTORY_DATA, theo dõi số agent sẵn sàng"),
       ("Time Server", "src/server/gcs_server.c", "Socket UDP :9091; đóng dấu T2 ngay sau khi nhận, T3 ngay trước khi gửi"),
       ("Multicast Announcer", "src/server/gcs_server.c", "Mỗi 250 ms phát HEARTBEAT; khi mọi agent đã có quỹ đạo thì chốt "
                                                       "T_{target} và phát SHOW_ARM_TRIGGER"),
       ("Clock Discipline", "src/agent/drone_agent.c", "K lần trao đổi bốn mốc thời gian, giữ mẫu RTT nhỏ nhất"),
       ("Trigger Scheduler", "src/agent/drone_agent.c", "Hẹn giờ tuyệt đối (timerfd) tới khi đồng hồ đã hiệu chỉnh = "
                                                     "T_{target}"),
       ("Failsafe + Geofence", "src/agent/failsafe.c, src/common/geofence.c", "Mất heartbeat > 2000 ms → AUTO_HOVER; ra khỏi hộp "
                                                                      "3D hoặc pin < 10 % → NAV_LAND"),
       ("SITL Flight", "scripts/sitl_flight.py", "Kiểm tra đúng tiến trình PX4 SITL, OFFBOARD, ARM, bay 4 điểm mốc, LAND"),
       ("Baseline", "src/server/baseline_server.c, src/agent/baseline_agent.c", "Hệ tham chiếu phát điểm đặt unicast 10 Hz")],
      "Thành phần của hệ thống", widths=[3.4, 4.6, 8.0], mono_cols=(1,))
    H("3.4. Luồng dữ liệu và nguyên lý hoạt động", 2)
    P("Hệ thống vận hành theo bốn pha (Hình 2). Pha 1 và 2 diễn ra khi drone còn dưới đất, không chịu ràng buộc thời "
      "gian thực. Pha 3 chỉ có một loại gói nhỏ phát cho cả nhóm. Ở pha 4, mạng chỉ mang heartbeat; **quỹ đạo lấy từ bộ "
      "nhớ của chính agent**, nên mất gói trong lúc bay không làm thay đổi điểm đặt. Mạng hỏng hẳn quá 2 s thì "
      "failsafe tự kích hoạt tại từng drone, không cần lệnh từ GCS.")
    F(DG / "h02_luong_du_lieu.png", "Trình tự trao đổi bản tin theo bốn pha vận hành")
    H("3.5. Giao thức tầng ứng dụng DLSP", 2)
    P("Mọi bản tin giữa GCS và agent dùng chung một khung (Hình 3). Header cố định 16 byte, các số nguyên nhiều byte ở "
      "thứ tự byte mạng (big-endian) qua các hàm `put16/put32/put64` tương đương `htons/htonl`. Trường `RESERVED` bổ sung "
      "so với bản phác thảo ban đầu để header tròn 16 byte. CRC-16/CCITT-FALSE [13] tính trên toàn khung với hai byte "
      "checksum coi bằng 0; bên nhận loại khung nếu sai magic, version, type ngoài 0x01–0x09, reserved khác 0, độ dài "
      "không khớp hoặc sai CRC.")
    F(DG / "h03_khung_tin.png", "Cấu trúc khung tin DLSP")
    T([("Mã", "Bản tin", "Kênh, hướng", "Payload", "Khung"),
       ("0x01", "HELLO_REQ", "TCP, Agent → GCS", "drone_id u16", "18 B"),
       ("0x02", "HELLO_ACK", "TCP, GCS → Agent", "drone_id u16", "18 B"),
       ("0x03", "TRAJECTORY_DATA", "TCP, GCS → Agent", "drone_id u16, số điểm u16, mỗi điểm 23 B: t_ms u32, x, y, z, yaw "
                                                        "float32, r, g, b u8", "16 + 4 + 23M B"),
       ("0x04", "TIME_SYNC_REQ", "UDP unicast, Agent → GCS", "T1 u64 (µs)", "24 B"),
       ("0x05", "TIME_SYNC_RESP", "UDP unicast, GCS → Agent", "T1, T2, T3 u64 (µs)", "40 B"),
       ("0x06", "SWARM_HEARTBEAT", "UDP multicast, GCS → nhóm", "rỗng", "16 B"),
       ("0x07", "SHOW_ARM_TRIGGER", "UDP multicast, GCS → nhóm", "T_{target} u64 (µs, đồng hồ GCS)", "24 B"),
       ("0x08", "EMERGENCY_STOP", "UDP multicast (baseline: TCP)", "rỗng", "16 B"),
       ("0x09", "SETPOINT", "TCP, GCS → Agent (baseline)", "drone_id, t_ms, x, y, z, yaw, r, g, b", "41 B")],
      "Danh mục bản tin DLSP", widths=[1.5, 4.5, 3.6, 4.6, 1.8], align=[C, L, L, L, C], mono_cols=(1,))
    P("**Tách khung trên dòng TCP.** TCP không giữ ranh giới bản tin: một lần `recv` có thể trả về nửa header hoặc hai "
      "bản tin dính nhau. Bên nhận đọc đủ 16 byte header, lấy `PAYLOAD_LEN`, kiểm tra không vượt bộ đệm rồi mới đọc tiếp "
      "phần tải. GCS giữ bộ đệm riêng cho từng kết nối non-blocking và chỉ xử lý khi đã ghép đủ khung; kiểm thử tích hợp "
      "gửi HELLO_REQ từng byte một để xác nhận cơ chế này.")
    P("**Chống trùng lặp trên UDP.** Agent bỏ qua mọi gói multicast có `SEQ_NUM` không lớn hơn số đã nhận, nên GCS có "
      "thể phát lặp SHOW_ARM_TRIGGER nhiều lần (4 Hz cho tới 1 s sau T_{target}) để chống mất gói mà agent vẫn chỉ kích "
      "hoạt một lần.")
    H("3.6. Hệ tham chiếu (baseline) và so sánh", 2)
    H("3.6.1. Kiến trúc baseline: phát điểm đặt unicast thời gian thực", 3)
    P("Hệ tham chiếu mô phỏng cách làm phổ biến (Hình 4): GCS giữ toàn bộ kịch bản; trong suốt buổi diễn, cứ 100 ms "
      "GCS tính điểm đặt hiện tại của từng drone và gửi một bản tin SETPOINT 41 byte qua kết nối TCP riêng của drone đó, "
      "lần lượt i = 1 … N. Agent không có quỹ đạo, chỉ chuyển tiếp điểm đặt nhận được; gói nào không tới thì drone giữ "
      "điểm đặt cũ. Lệnh bắt đầu cũng chính là SETPOINT đầu tiên gửi tuần tự. Baseline dùng chung bộ mã giao thức "
      "`src/common/protocol.c` với hệ đề xuất để so sánh chỉ phản ánh khác biệt kiến trúc.")
    F(DG / "h04_baseline.png", "Kiến trúc hệ tham chiếu baseline")
    H("3.6.2. So sánh đặc tính", 3)
    T([("Tiêu chí", "Baseline (unicast streaming)", "Đề xuất (nạp trước + multicast)"),
       ("Lưu lượng khi bay", "N luồng × 10 Hz × 41 B", "1 luồng heartbeat 4 Hz × 16 B"),
       ("Bậc băng thông theo N", "O(N)", "O(1)"),
       ("Nguồn gốc lệch khởi động", "Gửi tuần tự N lệnh + trễ riêng từng đường", "Sai số đồng hồ sau đồng bộ"),
       ("Nguồn điểm đặt khi bay", "Mạng, theo thời gian thực", "Bộ nhớ của agent"),
       ("Khi mất gói", "Giữ điểm đặt cũ, sai lệch quỹ đạo", "Chỉ mất heartbeat, quỹ đạo không đổi"),
       ("Khi GCS ngừng hoạt động", "Drone đứng tại điểm đặt cuối", "Failsafe tự kích hoạt sau 2 s"),
       ("Đồng bộ đồng hồ", "Không cần", "Bắt buộc, có cận sai số"),
       ("Độ phức tạp hiện thực", "Thấp", "Trung bình"),
       ("Linh hoạt sửa quỹ đạo khi bay", "Cao", "Thấp, phải nạp lại")],
      "So sánh đặc tính hai kiến trúc", widths=[4.6, 5.7, 5.7])
    H("3.6.3. Điểm cải tiến so với hệ thống hiện có", 3)
    B(["**Tách kênh dữ liệu và kênh thời gian.** Dữ liệu lớn đi trước qua TCP; trong lúc bay mạng chỉ còn nhiệm vụ "
       "giữ nhịp. Chất lượng trình diễn không còn phụ thuộc chất lượng mạng tức thời.",
       "**Kích hoạt bằng mốc thời gian tuyệt đối thay vì bằng thời điểm nhận gói.** Gói trigger mang T_{target} ở tương "
       "lai (trước 1,5 s); trễ của chính gói trigger không ảnh hưởng thời điểm bắt đầu, chỉ có sai số đồng hồ ảnh hưởng.",
       "**Bộ lọc chọn mẫu RTT nhỏ nhất** cho đồng bộ Cristian, có cận sai số tính được cho từng drone.",
       "**Failsafe phân tán**: mỗi drone tự phát hiện mất heartbeat, không có điểm lỗi đơn tại GCS.",
       "**Khung đánh giá có đối chứng**: hai kiến trúc chạy cùng kịch bản, cùng mô hình kênh, cùng chỉ số."], numbered=True)


# ============================================================ 4
def ch4():
    H("4. Mô hình toán học và phát biểu bài toán", 1)
    H("4.1. Ký hiệu", 2)
    T([("Ký hiệu", "Ý nghĩa", "Đơn vị"),
       ("N", "Số drone trong đàn", "–"), ("M", "Số điểm mốc quỹ đạo của một drone", "–"),
       ("p_{i}^{*}(t), p_{i}(t)", "Vị trí thiết kế và vị trí thực hiện của drone i", "m"),
       ("C_{i}(t)", "Giá trị đồng hồ cục bộ của drone i tại thời điểm thực t", "s"),
       ("θ_{i}, θ̂_{i}", "Độ lệch đồng hồ chủ so với drone i và giá trị ước lượng", "s"),
       ("T1…T4", "Bốn mốc thời gian của một lần đồng bộ", "s"),
       ("d₁, d₂", "Trễ một chiều chiều đi (agent → GCS) và chiều về", "s"), ("R", "Thời gian khứ hồi đã trừ thời gian xử lý", "s"),
       ("ε", "Cận sai số ước lượng độ lệch đồng hồ", "s"), ("K", "Số mẫu đồng bộ", "–"),
       ("T_{target}", "Thời điểm bắt đầu theo đồng hồ GCS", "s"), ("τ_{i}", "Thời điểm thực drone i bắt đầu", "s"),
       ("σ_{start}", "Độ lệch khởi động toàn đàn = max τ_{i} − min τ_{i}", "s"),
       ("f_{s}, T_{s}", "Tần số và chu kỳ phát điểm đặt của baseline (10 Hz, 0,1 s)", "Hz, s"),
       ("f_{hb}", "Tần số heartbeat của hệ đề xuất (4 Hz)", "Hz"), ("S", "Kích thước khung tin", "byte"),
       ("B", "Băng thông chiều xuống trong lúc bay", "byte/s"), ("p", "Tỷ lệ mất gói", "–"),
       ("v", "Vận tốc drone", "m/s"), ("d_{safe}", "Khoảng cách an toàn tối thiểu", "m"),
       ("e_{i}(t)", "Sai số vị trí tức thời ‖p_{i}(t) − p_{i}^{*}(t)‖", "m")],
      "Bảng ký hiệu", widths=[3.4, 10.4, 2.2], align=[C, L, C])
    H("4.2. Phát biểu bài toán", 2)
    P("**Đầu vào:** kịch bản trình diễn S = {(t_{k}, x, y, z, yaw, r, g, b)} cho từng drone; quy mô N; tham số kênh "
      "(trễ trung bình, tỷ lệ mất gói p); độ lệch đồng hồ ban đầu của từng drone; giới hạn vận tốc và khoảng cách an toàn.")
    P("**Đầu ra:** thời điểm bắt đầu τ_{i} và chuỗi điểm đặt của từng drone; các chỉ số σ_{start}, B, E_{RMS}, sai số đồng hồ "
      "và thời gian phát hiện mất liên lạc.")
    P("**Giả thiết:**")
    B(["G1. Trong một buổi diễn, đồng hồ mỗi nút lệch đồng hồ chủ một hằng số θ_{i} (bỏ qua trôi tần số trong vài phút; "
       "Mục 4.3.4 xét trôi).",
       "G2. Trễ hai chiều có cùng phân phối: E[d₁] = E[d₂] (cơ sở của mọi phương pháp đồng bộ dựa trên RTT).",
       "G3. Mất gói độc lập, cùng xác suất p (mô hình Bernoulli).",
       "G4. Bộ nhớ drone đủ chứa quỹ đạo của chính nó: 23 byte/điểm, 10 điểm/s, 10 phút ≈ 138 KB.",
       "G5. Nạp quỹ đạo và đồng bộ đồng hồ diễn ra khi drone còn dưới đất."])
    P("**Ràng buộc:**")
    EQ(r"\left\|p_i(t)-p_j(t)\right\| \ge d_{safe},\quad \forall i\ne j,\ \forall t", "4.1")
    EQ(r"\left\|\dot p_i(t)\right\| \le v_{max},\qquad B \le B_{max},\qquad \sigma_{start} \le \sigma_{max}", "4.2")
    P("Với yêu cầu sai lệch vị trí do lệch thời gian không quá δ = 5 cm ở v = 2 m/s, cần σ_{max} = δ / v = 25 ms.")
    P("**Hàm mục tiêu.** Biến quyết định ở cấp thiết kế là kiến trúc truyền thông Π ∈ {Π_{base}, Π_{prop}}. Bài toán là chọn "
      "Π cực tiểu tổ hợp chuẩn hóa của ba chỉ số, với ràng buộc (4.1)–(4.2):")
    EQ(r"\min_{\Pi} J(\Pi)=w_1\frac{\sigma_{start}(\Pi)}{\sigma_{max}}+w_2\frac{E_{RMS}(\Pi)}{d_{safe}}+w_3\frac{B(\Pi)}{B_{max}}", "4.3")
    P("trong đó w_{1} = w_{2} = 0,4 và w_{3} = 0,2 (ưu tiên chất lượng hình ảnh hơn băng thông). Các mục sau xây dựng biểu "
      "thức của từng thành phần cho mỗi kiến trúc.")
    H("4.3. Mô hình đồng bộ đồng hồ", 2)
    H("4.3.1. Trao đổi bốn mốc thời gian", 3)
    P("Agent ghi T1 trước khi gửi yêu cầu và T4 khi nhận trả lời, theo đồng hồ của nó; GCS ghi T2 ngay khi nhận và T3 "
      "ngay trước khi gửi, theo đồng hồ chủ (Hình 5). Gọi θ là lượng đồng hồ chủ nhanh hơn đồng hồ agent:")
    F(DG / "h05_bon_moc.png", "Bốn mốc thời gian trong một lần đồng bộ", width_cm=12.5)
    EQ(r"T_2 = T_1 + \theta + d_1,\qquad T_4 = T_3 - \theta + d_2", "4.4")
    P("Cộng và trừ hai đẳng thức, với giả thiết G2 (d₁ = d₂):")
    EQ(r"\hat\theta=\frac{(T_2-T_1)+(T_3-T_4)}{2},\qquad R=(T_4-T_1)-(T_3-T_2)=d_1+d_2", "4.5")
    P("Khi bỏ qua thời gian xử lý (T2 = T3 = T_{s}erver), (4.5) trở về dạng Cristian quen thuộc "
      "θ̂ = T_{s}erver + RTT/2 − T_client.")
    H("4.3.2. Cận sai số", 3)
    P("Từ (4.4), sai số ước lượng bằng nửa độ bất đối xứng của kênh. Vì cả hai trễ không âm và tổng bằng R:")
    EQ(r"\hat\theta-\theta=\frac{d_1-d_2}{2}\quad\Rightarrow\quad \left|\hat\theta-\theta\right|\le\frac{R}{2}=\varepsilon", "4.6")
    P("Cận (4.6) **không cần giả thiết G2**: dù kênh bất đối xứng đến đâu, sai số vẫn không vượt R/2. Mỗi agent tự tính "
      "được ε của mình.")
    H("4.3.3. Bộ lọc chọn mẫu RTT nhỏ nhất", 3)
    P("Từ (4.6), mẫu có R nhỏ nhất cho cận sai số chặt nhất. Với K mẫu, agent chọn:")
    EQ(r"k^*=\underset{k=1..K}{\arg\min}\,R_k,\qquad \hat\theta=\hat\theta_{k^*},\qquad \varepsilon=\frac{R_{k^*}}{2}", "4.7")
    P("Trễ hàng đợi trên mạng chuyển mạch gói có đuôi phải dài; mẫu có R nhỏ nhất là mẫu ít bị xếp hàng nhất ở cả hai "
      "chiều, nên độ bất đối xứng của nó cũng nhỏ. Khi K tăng, min R_{k} tiến về trễ truyền tối thiểu của kênh. So với "
      "lấy trung bình K mẫu, bộ lọc này loại hẳn các mẫu bị trễ đột biến thay vì chỉ làm loãng chúng. Bộ lọc chỉ cần "
      "nhớ một mẫu tốt nhất: thời gian O(K), bộ nhớ O(1).")
    H("4.3.4. Trôi đồng hồ", 3)
    P("Bộ dao động thạch anh thông thường có sai số tần số |ρ| ≤ 50 ppm. Sau Δt giây kể từ lần đồng bộ, sai số tăng "
      "thêm |ρ|·Δt. Để phần này không quá 5 ms cần Δt ≤ 5·10⁻³ / 5·10⁻⁵ = 100 s. Bản hiện thực đồng bộ ngay trước khi "
      "nhận trigger (Δt ≈ 1,5 s, sai số trôi ≤ 75 µs); với buổi diễn dài, agent cần đồng bộ lại định kỳ (Mục 7.4).")
    H("4.4. Mô hình độ lệch khởi động", 2)
    P("**Hệ đề xuất.** Drone i bắt đầu khi đồng hồ cục bộ đã hiệu chỉnh bằng T_{target}, tức tại thời điểm thực "
      "τ_{i} = T_{target} + (θ_{i} − θ̂_{i}) + w_{i}, với w_{i} là độ trễ đánh thức tiến trình của hệ điều hành. Do đó:")
    EQ(r"\sigma_{start}^{prop}\le \max_i\varepsilon_i+\max_i\varepsilon_i+\max_i w_{i} \le \max_i R_i+\max_i w_{i}", "4.8")
    P("Biểu thức không chứa N và không chứa trễ của gói trigger: lệch khởi động chỉ do chất lượng đồng bộ.")
    P("**Baseline.** GCS gửi lệnh bắt đầu lần lượt cho N drone, mỗi lần gửi tốn τ_{tx}; drone i nhận sau thêm trễ d_{i}:")
    EQ(r"\tau_i^{base}=t_0+(i-1)\,\tau_{tx}+d_i\quad\Rightarrow\quad\sigma_{start}^{base}\approx(N-1)\,\tau_{tx}+\left(\max_i d_i-\min_i d_i\right)", "4.9")
    P("Độ lệch tăng tuyến tính theo N và cộng trực tiếp toàn bộ biến thiên trễ của kênh.")
    H("4.5. Mô hình băng thông", 2)
    EQ(r"B_{base}(N)=N\,f_s\,S_{sp}=N\cdot10\cdot41=410\,N\ \ \text{byte/s},\qquad B_{prop}=f_{hb}\,S_{hb}=4\cdot16=64\ \ \text{byte/s}", "4.10")
    EQ(r"\eta(N)=\frac{B_{base}(N)}{B_{prop}}=\frac{410\,N}{64}\approx 6{,}4\,N", "4.11")
    P("Hệ đề xuất phải trả thêm lượng dữ liệu nạp trước N·(20 + 23M) byte qua TCP và 64 byte mỗi lần đồng bộ, nhưng "
      "toàn bộ nằm ngoài thời gian bay. Trong lúc bay, lưu lượng không phụ thuộc N.")
    H("4.6. Mô hình sai số vị trí khi mất gói", 2)
    P("Xét baseline: drone thiết kế bay thẳng với vận tốc v, điểm đặt phát mỗi T_{s}. Nếu ở một chu kỳ, m gói liên tiếp "
      "gần nhất đều bị mất, drone đang giữ điểm đặt cũ m chu kỳ và sai số là e = m·v·T_{s}. Với mất gói độc lập xác suất "
      "p, m có phân phối hình học P(m = k) = (1 − p)·p^k, nên:")
    EQ(r"E[m]=\frac{p}{1-p},\qquad E[m^2]=\frac{p(1+p)}{(1-p)^2}", "4.12")
    EQ(r"E[e^{base}]=v\,T_{s}\,\frac{p}{1-p}", "4.13")
    EQ(r"E_{RMS}^{base}=\sqrt{E[e^2]}=v\,T_{s}\,\frac{\sqrt{p(1+p)}}{1-p}", "4.14")
    P("Với v = 2 m/s, T_{s} = 0,1 s, (4.14) cho 2,03 cm ở p = 1 % và 12,25 cm ở p = 20 %. Đuôi phân phối hình học sinh ra "
      "các chuỗi mất dài hiếm gặp, nên sai số cực đại lớn hơn nhiều lần giá trị RMS.")
    P("Với hệ đề xuất, điểm đặt lấy từ bộ nhớ theo đồng hồ đã hiệu chỉnh nên mất gói không đổi điểm đặt. Sai số duy "
      "nhất do mạng là sai số thời gian:")
    EQ(r"e_i^{prop}=v\,|\hat\theta_i-\theta_i|\le v\,\varepsilon_i", "4.15")
    P("(4.15) không chứa p: theo mô hình, đường E_{RMS} của hệ đề xuất phải nằm ngang khi p tăng, cho tới khi mất "
      "heartbeat liên tục quá 2 s và failsafe kích hoạt. Điều kiện để baseline không vi phạm khoảng cách an toàn giữa "
      "hai drone liền kề cùng bị lệch là 2·max e < d_{safe}.")
    H("4.7. Mô hình máy trạng thái của Drone Agent", 2)
    P("Hành vi của agent là máy trạng thái hữu hạn M = (Q, Σ, δ, q0, F) với Q = {INIT, CONNECTED, LOADED, SYNCED, ARMED, "
      "SHOW_RUNNING, FAILSAFE, FINISHED}, q0 = INIT, F = {FINISHED, FAILSAFE} (Hình 6, Bảng 9). Mọi lỗi trước khi bay "
      "(TCP đóng, quỹ đạo sai định dạng, đồng bộ thất bại, mất heartbeat) đều kết thúc tiến trình với drone còn dưới "
      "đất. Sau khi bay, mọi đường đi đều kết thúc ở FINISHED hoặc FAILSAFE, kể cả khi GCS ngừng hẳn: không có trạng "
      "thái nào chờ GCS vô hạn.")
    F(DG / "h06_fsm.png", "Máy trạng thái hữu hạn của Drone Agent")
    T([("Trạng thái", "Sự kiện", "Trạng thái kế", "Hành động"),
       ("INIT", "TCP kết nối, nhận HELLO_ACK đúng id", "CONNECTED", "Đã gia nhập nhóm multicast"),
       ("CONNECTED", "Nhận TRAJECTORY_DATA hợp lệ", "LOADED", "Lưu quỹ đạo vào RAM"),
       ("LOADED", "Ít nhất một mẫu đồng bộ hợp lệ trong K lần", "SYNCED", "Lưu θ̂, R_{min}"),
       ("SYNCED", "SHOW_ARM_TRIGGER (seq mới, CRC đúng)", "ARMED", "Tính thời điểm thức tuyệt đối"),
       ("ARMED", "Đồng hồ hiệu chỉnh = T_{target}", "SHOW_RUNNING", "Ghi mốc bắt đầu"),
       ("SHOW_RUNNING", "Mất HB > 2000 ms", "FAILSAFE", "MAV_CMD_DO_SET_MODE: AUTO_HOVER"),
       ("SHOW_RUNNING", "Ra khỏi geofence / pin < 10 % / EMERGENCY_STOP", "FAILSAFE", "MAV_CMD_NAV_LAND"),
       ("SHOW_RUNNING", "Hết thời lượng", "FINISHED", "Kết thúc")],
      "Bảng chuyển trạng thái của Drone Agent", widths=[2.9, 5.5, 2.8, 4.8])
    H("4.8. Các dự báo cần kiểm chứng", 2)
    T([("Mã", "Dự báo", "Nguồn"),
       ("P1", "σ_{start} của baseline tăng theo N và theo biến thiên trễ; của hệ đề xuất bị chặn bởi max R + max w", "(4.8), (4.9)"),
       ("P2", "B_{base} tăng tuyến tính 410N byte/s; B_{prop} không đổi theo N", "(4.10), (4.11)"),
       ("P3", "E_{RMS} của baseline tăng theo (4.14); của hệ đề xuất không phụ thuộc p", "(4.14), (4.15)"),
       ("P4", "|θ̂ − θ| ≤ R/2 với mọi drone; bộ lọc RTT nhỏ nhất cho sai số nhỏ hơn lấy trung bình", "(4.6), (4.7)")],
      "Các dự báo lý thuyết", widths=[1.3, 11.7, 3.0], align=[C, L, C])


# ============================================================ 5
def ch5():
    H("5. Triển khai hệ thống và giải thuật", 1)
    H("5.1. Công nghệ và môi trường", 2)
    T([("Hạng mục", "Lựa chọn", "Lý do"),
       ("Phần cứng", "AMD Ryzen 7 4800H (8 nhân, 16 luồng), RAM 24 GB", "Máy cá nhân của nhóm"),
       ("Hệ điều hành", "Ubuntu 22.04.5 LTS, nhân Linux 6.8.0", "Có epoll, multicast; nền tảng PX4 hỗ trợ chính thức"),
       ("Ngôn ngữ mạng", "C11, gcc 11.4, cờ -Wall -Wextra -Werror", "Kiểm soát trực tiếp bố cục byte và socket POSIX"),
       ("Thư viện socket", "POSIX socket, epoll, poll", "Không dùng thư viện mạng bên ngoài"),
       ("Điều khiển bay", "PX4 Autopilot v1.14.4 SITL + jMAVSim", "Theo yêu cầu đề tài; jMAVSim nhẹ, khởi động nhanh"),
       ("Trạm mặt đất", "QGroundControl 4.4.5", "Quan sát độc lập trạng thái PX4"),
       ("MAVLink phía nhóm", "pymavlink 2.4.50 (Python 3)", "Kịch bản bay thử SITL"),
       ("Đo đạc, vẽ hình", "Python 3, matplotlib, pyulog", "Tự động hóa ma trận thực nghiệm, đọc ULog")],
      "Công nghệ và môi trường thực nghiệm", widths=[3.0, 6.5, 6.5])
    H("5.2. Cấu trúc mã nguồn", 2)
    T([("Tệp", "Nội dung"),
       ("src/common/protocol.h, protocol.c", "Mã bản tin, encode/decode, CRC-16 và big-endian"),
       ("src/common/stream.h, stream.c", "Gửi đủ byte, ghép khung TCP; xử lý EINTR và backpressure"),
       ("src/common/cli.h", "Kiểm tra miền giá trị các tham số dòng lệnh"),
       ("src/common/geofence.h, geofence.c", "Hộp giới hạn 3D hệ NED, từ chối tọa độ không hữu hạn"),
       ("src/server/gcs_server.c", "GCS đề xuất: epoll, Time Server, multicast"),
       ("src/agent/drone_agent.c", "Đồng bộ đồng hồ, timerfd, failsafe và mô phỏng kênh"),
       ("src/agent/failsafe.h, failsafe.c", "Giám sát heartbeat, geofence và pin; callback mô phỏng"),
       ("src/server/baseline_server.c, src/agent/baseline_agent.c", "Hệ tham chiếu unicast streaming"),
       ("scripts/", "Sinh kịch bản, chạy thực nghiệm, vẽ biểu đồ và bài bay SITL độc lập"),
       ("tests/", "Kiểm thử đơn vị và tích hợp TCP/UDP; kiểm thử MAVLink bằng mock")],
      "Các tệp mã nguồn chính", widths=[7.0, 9.0], align=[L, L], size=11)
    P("Mô-đun bổ sung src/common/spline.* nội suy Cubic Hermite 3D; tools/pattern_generator.py sinh ngôi sao và "
      "xoắn ốc với mốc vị trí, vận tốc và RGB. Dữ liệu đóng thành khung mở rộng 0x0A (SHOW_WAYPOINT_DATA), "
      "được kiểm thử độc lập. Mô-đun này chưa nối vào vòng phát quỹ đạo của GCS/agent và không tham gia "
      "các phép đo ngày 16/11/2026.")
    H("5.3. Các bước triển khai", 2)
    B(["**Giao thức.** Viết kiểm thử trước cho bố cục header, thứ tự byte, CRC, khung cụt, độ dài sai, version sai; "
       "sau đó hiện thực `encode/decode`.",
       "**GCS và agent tối thiểu.** Bắt tay HELLO, gửi quỹ đạo, phát heartbeat/trigger multicast; kiểm thử tích hợp với "
       "2 agent và HELLO gửi từng byte.",
       "**PX4 SITL.** Cài PX4 v1.14.4, jMAVSim, QGroundControl; viết kịch bản bay thử có kiểm tra an toàn: chỉ ARM khi "
       "đúng tiến trình PX4 SITL cục bộ đang chạy, heartbeat là PX4 quadrotor, chưa ARM; luôn gửi LAND khi kết thúc "
       "hoặc lỗi.",
       "**Failsafe và geofence.** Module độc lập, kiểm thử 4 tình huống: mất heartbeat, ra khỏi hộp, pin yếu, dừng khẩn.",
       "**Hệ tham chiếu.** Baseline src/server/agent dùng chung bộ mã giao thức.",
       "**Đồng bộ Cristian và kích hoạt theo T_{target}.** Thêm Time Server vào vòng epoll của GCS, thêm bộ lọc vào agent, "
       "trigger mang T_{target} tính bằng µs.",
       "**Đo đạc.** Khung đo tự động chạy hai kiến trúc trên cùng ma trận, các tiến trình tự in số đo (µs, byte, "
       "getrusage) để không phụ thuộc phép đo bên ngoài."], numbered=True)
    H("5.4. Giải thuật", 2)
    H("5.4.1. Vòng lặp sự kiện của GCS", 3)
    P("GCS là một luồng duy nhất. Ba loại socket (listener TCP, các kết nối agent, socket UDP đồng bộ) đều đăng ký vào "
      "cùng một epoll; phát multicast được gắn vào timeout 50 ms của `epoll_wait`. Hai mốc T2, T3 được lấy sát lời gọi "
      "`recvfrom`/`sendto` nhất có thể để thời gian xử lý không lọt vào RTT.")
    ALG("Thuật toán 1. Vòng lặp sự kiện GCS", [
        "Vào : show.bin, cổng TCP P, cổng đồng bộ P_s, nhóm G, lead = 1,5 s",
        " 1  đọc và kiểm tra show.bin; sai định dạng -> thoát trước khi mở socket",
        " 2  listener <- TCP(P), non-blocking ; sync <- UDP(P_s) ; mc <- UDP, IP_MULTICAST_IF",
        " 3  ep <- epoll_create ; đăng ký listener, sync",
        " 4  T_target <- 0 ; lặp tới khi nhận SIGTERM:",
        " 5      events <- epoll_wait(ep, 50 ms)",
        " 6      với mỗi ev:",
        " 7          ev = listener : accept tới EAGAIN, non-blocking, đăng ký EPOLLIN",
        " 8          ev = sync     : T2 <- now ; giải mã REQ ; T3 <- now ; gửi RESP(T1,T2,T3)",
        " 9          ev = agent    : ghép byte tới đủ 18 B ; kiểm tra HELLO_REQ, id chưa dùng",
        "10                          gửi HELLO_ACK + TRAJECTORY_DATA (EPOLLOUT, gửi từng phần)",
        "11      nếu mọi agent đã nhận quỹ đạo và T_target = 0 : T_target <- now + lead",
        "12      nếu đến chu kỳ 250 ms:",
        "13          nếu T_target > 0 và now < T_target + 1 s : multicast TRIGGER(T_target)",
        "14          ngược lại : multicast HEARTBEAT",
        "15  in số khung, số byte multicast, thời gian CPU (getrusage)"])
    F(DG / "h07_luu_do_gcs.png", "Lưu đồ vòng lặp sự kiện của GCS", width_cm=11.5)
    H("5.4.2. Đồng bộ đồng hồ có lọc chọn mẫu", 3)
    ALG("Thuật toán 2. Đồng bộ Cristian bốn mốc thời gian, chọn mẫu RTT nhỏ nhất", [
        "Vào : K, địa chỉ Time Server ; Ra : θ̂, ε",
        " 1  R_min <- +∞",
        " 2  với k = 1..K:",
        " 3      T1 <- đồng hồ cục bộ (µs) ; gửi TIME_SYNC_REQ(T1)",
        " 4      chờ trả lời tối đa 200 ms ; T4 <- đồng hồ cục bộ",
        " 5      nếu quá hạn, sai CRC, sai kiểu hoặc T1 trả về khác T1 đã gửi : bỏ mẫu",
        " 6      R <- (T4 - T1) - (T3 - T2) ; θ <- ((T2 - T1) + (T3 - T4)) / 2",
        " 7      nếu R < R_min : R_min <- R ; θ̂ <- θ",
        " 8      nghỉ 2 ms",
        " 9  nếu không có mẫu hợp lệ : báo lỗi, không cất cánh",
        "10  trả về θ̂, ε = R_min / 2"])
    F(DG / "h08_luu_do_sync.png", "Lưu đồ thuật toán đồng bộ đồng hồ", width_cm=11)
    P("Việc kiểm tra T1 trả về trùng với T1 đã gửi (bước 5) loại các trả lời muộn của mẫu trước, tránh ghép nhầm "
      "T2, T3 của lần này với T1 của lần khác.")
    H("5.4.3. Thực thi phân tán tại Drone Agent", 3)
    ALG("Thuật toán 3. Kích hoạt và giám sát tại agent", [
        " 1  gia nhập nhóm G ; TCP connect ; HELLO_REQ ; nhận HELLO_ACK + quỹ đạo vào RAM",
        " 2  (θ̂, ε) <- Thuật toán 2",
        " 3  khởi tạo failsafe: timeout HB 2000 ms, geofence ±50 m, trần 50 m",
        " 4  lặp: poll(socket multicast, timerfd, 200 ms)",
        " 5      nhận gói: nếu sai CRC hoặc seq ≤ seq_cuối : bỏ ; seq_cuối <- seq",
        " 6          cập nhật thời điểm HB cuối",
        " 7          nếu TRIGGER và chưa bay:",
        " 8              đặt timerfd tuyệt đối sao cho cục bộ + θ̂ = T_target",
        " 9      nếu timerfd hết hạn: ghi mốc bắt đầu ; SHOW_RUNNING",
        "10      nếu SHOW_RUNNING:",
        "11          điểm đặt <- quỹ đạo trong RAM tại t = cục bộ + θ̂ - T_target",
        "12          nếu failsafe_check(HB, vị trí, pin) vi phạm : gửi lệnh an toàn, FAILSAFE",
        "13          nếu hết thời lượng : FINISHED"])
    F(DG / "h09_luu_do_agent.png", "Lưu đồ thực thi tại Drone Agent", width_cm=11)
    P("Dùng hẹn giờ **tuyệt đối** thay vì tương đối là chi tiết quan trọng: thời gian xử lý gói trigger và trễ của chính "
      "gói trigger không cộng vào thời điểm bắt đầu.")
    H("5.4.4. Thuật toán của hệ tham chiếu", 3)
    ALG("Thuật toán 4. Baseline: phát điểm đặt unicast thời gian thực", [
        "GCS:",
        " 1  chờ đủ N agent HELLO (epoll) ; chỉ gửi HELLO_ACK, không gửi quỹ đạo",
        " 2  với i = 1..N : gửi SETPOINT(t = 0) cho agent i        # lệnh bắt đầu tuần tự",
        " 3  mỗi 100 ms tới hết thời lượng:",
        " 4      với i = 1..N : x_i <- x0_i + v·t ; gửi SETPOINT(x_i) qua TCP của agent i",
        " 5  gửi EMERGENCY_STOP ; in băng thông, độ lệch gửi, CPU",
        "Agent:",
        " 6  khi nhận SETPOINT đầu tiên : ghi mốc bắt đầu",
        " 7  với mỗi SETPOINT: nếu gói bị mất (xác suất p) : giữ điểm đặt cũ",
        " 8                     ngược lại : điểm đặt <- x nhận được",
        " 9      sai số <- |điểm đặt đang giữ - x thiết kế|"])
    F(DG / "h10_luu_do_baseline.png", "Lưu đồ hệ tham chiếu baseline", width_cm=11)
    H("5.4.5. Độ phức tạp", 3)
    T([("Thao tác", "Thời gian", "Bộ nhớ", "Ghi chú"),
       ("GCS: một vòng epoll", "O(k)", "O(N)", "k sự kiện sẵn sàng; select/poll là O(N)"),
       ("GCS: phát lệnh mỗi chu kỳ – baseline", "O(N)", "O(1)", "N lời gọi send"),
       ("GCS: phát lệnh mỗi chu kỳ – đề xuất", "O(1)", "O(1)", "Một lời gọi sendto multicast"),
       ("GCS: nạp quỹ đạo (một lần)", "O(N·M)", "O(N·M)", "Ngoài thời gian bay"),
       ("Agent: đồng bộ", "O(K)", "O(1)", "Chỉ giữ mẫu tốt nhất"),
       ("Agent: tra điểm đặt", "O(1)", "O(M)", "Con trỏ chạy theo thời gian đơn điệu"),
       ("Giải mã khung, CRC-16", "O(L)", "O(1)", "L là độ dài khung")],
      "Độ phức tạp thuật toán", widths=[5.8, 2.0, 2.0, 6.2], align=[L, C, C, L])
    H("5.5. Mô phỏng điều kiện mạng", 2)
    P("Công cụ `tc netem` tác động lên toàn bộ giao diện mạng và cần quyền root, nên không dùng để tránh thay đổi cấu "
      "hình máy. Thay vào đó, cả hai loại agent nhận cùng một mô hình kênh ở tầng ứng dụng, điều khiển bằng tham số "
      "dòng lệnh:")
    B(["**Lệch đồng hồ** (`--clock-offset-ms`): đồng hồ agent = đồng hồ thực + θ_{i}, θ_{i} rút ngẫu nhiên đều trong "
       "[−50; 50] ms. Mọi mốc thời gian agent dùng để đồng bộ và để chờ T_{target} đều đọc qua đồng hồ lệch này.",
       "**Trễ hàng đợi** (`--jitter-ms`): mỗi gói gửi và nhận bị giữ thêm một khoảng ngẫu nhiên phân phối mũ với trung "
       "bình cho trước, độc lập hai chiều, nên kênh bất đối xứng ngẫu nhiên đúng như thực tế.",
       "**Mất gói** (`--loss`): mỗi gói bị bỏ với xác suất p, độc lập (giả thiết G3)."])
    P("Mốc thời gian dùng để **chấm điểm** (thời điểm bắt đầu thực, thời điểm phát hiện failsafe) luôn đọc từ đồng hồ "
      "thực `CLOCK_REALTIME` của máy, chung cho mọi tiến trình, nên phép đo không bị ảnh hưởng bởi đồng hồ giả lập.")
    H("5.6. Cấu hình thử nghiệm", 2)
    T([("Tham số", "Giá trị"),
       ("Cổng TCP / UDP đồng bộ / nhóm multicast", "8080 / 9091 / 239.255.0.1:9090 (khi đo dùng cổng trống ngẫu nhiên)"),
       ("Chu kỳ heartbeat của GCS", "250 ms (4 Hz)"), ("Thời gian báo trước T_{target}", "1,5 s"),
       ("Số mẫu đồng bộ K", "8 (TN-4 dùng 16)"), ("Timeout heartbeat (failsafe)", "2000 ms"),
       ("Geofence", "x, y ∈ [−50; 50] m, độ cao ≤ 50 m"),
       ("Baseline: tần số / kích thước điểm đặt", "10 Hz / 41 byte"), ("Vận tốc thiết kế v", "2 m/s"),
       ("Lệch đồng hồ ban đầu", "U(−50; 50) ms, hạt giống ngẫu nhiên 2026"),
       ("Kịch bản", "Đội hình trái tim, N drone, sinh bởi generate_show.py")],
      "Tham số hệ thống khi thực nghiệm", widths=[7.0, 9.0])
    T([("Mã", "Mục tiêu", "Biến thay đổi", "Lặp", "Chỉ số"),
       ("TN-1", "Mở rộng quy mô", "N ∈ {2, 5, 10, 20, 50, 100}", "3", "σ_{start}, B, CPU của GCS"),
       ("TN-2", "Ảnh hưởng trễ", "Trễ TB 0, 1, 5, 10, 20 ms; N = 20", "3", "σ_{start}, |θ̂ − θ|, ε"),
       ("TN-3", "Ảnh hưởng mất gói", "p ∈ {0, 1, 5, 10, 20} %; N = 20", "5", "E_{RMS}, max e, số drone khởi động"),
       ("TN-4", "Hiệu quả bộ lọc", "K ∈ {1, 2, 4, 8, 16}; trễ 1 và 5 ms", "5", "Phân bố θ̂ − θ"),
       ("TN-5", "Failsafe", "Tắt GCS (SIGKILL) khi đang bay; N = 10", "3", "Thời gian phát hiện"),
       ("TN-6", "Tích hợp PX4", "1 drone SITL, 4 điểm mốc", "1", "Độ cao, sai số bám, mất gói MAVLink")],
      "Ma trận thực nghiệm", widths=[1.4, 3.0, 5.6, 1.2, 4.8], align=[C, L, L, C, L])
    H("5.7. Kiểm thử", 2)
    P("Lệnh `make test` biên dịch toàn bộ với `-Werror` và chạy sáu nhóm kiểm thử (Hình 11). Độ phủ dòng lệnh đo bằng "
      "gcov: `protocol.c` 100 % (44/44 dòng), `geofence.c` 94,4 %, `failsafe.c` 79,3 %. Kiểm thử PX4 dùng đối tượng "
      "giả lập nên không bao giờ ARM phương tiện thật.")
    F(EV / "hinh_make_test.png", "Kết quả chạy make test", width_cm=12.5)


# ============================================================ 6
def ch6():
    H("6. Phân tích và đánh giá hiệu năng", 1)
    H("6.1. Chỉ số đánh giá và cách đo", 2)
    T([("Chỉ số", "Định nghĩa", "Cách đo"),
       ("σ_{start}", "max τ_{i} − min τ_{i}", "Mỗi agent in thời điểm bắt đầu theo CLOCK_REALTIME (µs)"),
       ("B", "Byte/s GCS gửi xuống trong lúc bay", "GCS tự cộng số byte của mọi lời gọi gửi thành công, chia thời gian"),
       ("CPU", "% một lõi GCS dùng", "getrusage(RUSAGE_SELF) khi GCS kết thúc / thời gian chạy"),
       ("|θ̂ − θ|, ε", "Sai số ước lượng đồng hồ và cận R_{min}/2", "Agent in θ̂, R_min; θ thật biết từ tham số giả lập"),
       ("E_{RMS}, max e", "Sai số điểm đặt so với thiết kế", "Baseline: agent tính mỗi chu kỳ; đề xuất: v·|θ̂ − θ| (4.15)"),
       ("Phát hiện failsafe", "Từ lúc tắt GCS tới lúc agent báo FAILSAFE", "Hai mốc CLOCK_REALTIME"),
       ("Sai số bám PX4", "‖vị trí EKF2 − điểm mốc‖", "Đọc ULog bằng pyulog"),
       ("Mất gói MAVLink", "Khoảng trống số thứ tự 8 bit", "Đếm số thứ tự tại máy thu; uORB telemetry_status")],
      "Chỉ số đánh giá", widths=[3.0, 5.0, 8.0])
    P("Số liệu trong chương này được đo tự động bằng khung thực nghiệm mô tả ở Mục 5.6; mỗi ô là trung bình ± "
      "độ lệch chuẩn qua các lần lặp.")

    P("Các kết quả định lượng được thu ngày 16/11/2026 trước đợt chỉnh lý mã nguồn ngày 18/11/2026. "
      "Bản bàn giao tách các mô-đun dùng chung, bổ sung kiểm tra đầu vào và thay chờ chặn bằng timerfd để tiếp nhận "
      "lệnh khẩn cấp khi chờ giờ diễn. Số liệu gốc được lưu cùng bài nộp; các giá trị thời gian và CPU phụ thuộc "
      "phiên bản phần mềm và môi trường chạy.")
    H("6.2. Kiểm chứng chức năng", 2)
    H("6.2.1. Đàn 4 agent với đồng hồ lệch nhau", 3)
    P("Hình 12 là đầu ra thật của 4 agent có đồng hồ lệch +45, +8, −29 và +24 ms, trễ hàng đợi trung bình 1 ms. Sau 8 "
      "mẫu đồng bộ, θ̂ của từng agent sai so với giá trị thật 23, 24, 408 và 33 µs, đều nhỏ hơn ε tương ứng (432–611 µs). "
      "Bốn agent bắt đầu trong khoảng 456 µs dù đồng hồ ban đầu lệch nhau tới 74 ms. GCS phát 5 khung multicast (112 "
      "byte) trong 1,1 s và dùng 3,6 ms CPU.")
    F(EV / "hinh_run_swarm4.png", "Đầu ra thực tế khi chạy GCS và 4 agent có đồng hồ lệch nhau")
    H("6.2.2. Khung tin bắt được trên nhóm multicast", 3)
    tr = FR["trigger"]
    P("Một tiến trình gia nhập nhóm 239.255.0.1 như một agent và ghi lại nguyên văn các khung GCS phát ra (Hình 13). "
      f"Cả bốn khung đều có magic 0x5058, version 1, reserved 0 và CRC khớp khi tính lại độc lập. Khung trigger dài "
      f"{tr['size']} byte, payload {tr['payload_len']} byte là T_{{target}} dạng u64 big-endian; heartbeat chỉ có header 16 "
      "byte. Khung TIME_SYNC_RESP mang lại đúng T1 của yêu cầu, sau đó là T2 và T3 cách nhau 3 µs, cho thấy thời gian xử "
      "lý tại Time Server rất nhỏ.")
    F(EV / "hinh_frames.png", "Bốn khung DLSP bắt được và giải mã")
    H("6.2.3. Tích hợp PX4 SITL", 3)
    P("PX4 v1.14.4 SITL chạy cùng jMAVSim và QGroundControl 4.4.5 (Hình 14). Kịch bản `sitl_flight.py` gửi heartbeat, "
      "phát điểm đặt 10 Hz trong 2 s, chuyển OFFBOARD, ARM, bay qua bốn điểm mốc NED (0, 0, −2), (2, 0, −2), (2, 2, −2), "
      "(0, 0, −2), mỗi điểm giữ 5 s, rồi gửi LAND. Hình 15 là dữ liệu đọc trực tiếp từ bus uORB của PX4.")
    F(EV / "hinh10_px4_sitl.png", "PX4 SITL trên jMAVSim (trái) và QGroundControl 4.4.5 (phải)")
    F(EV / "hinh11_uorb_listener.png", "Bản tin uORB vehicle_local_position đọc bằng px4-listener", width_cm=12)
    P("Nhật ký ULog của chuyến bay được trích xuất bằng thư viện pyulog [14]; kết quả trình bày ở Hình 16 và Bảng 18.")
    F(EV / "hinh_ulog_flight.png", "Chuyến bay PX4 SITL đọc từ ULog: độ cao, vị trí ngang, quỹ đạo nhìn từ trên")
    T([("Đại lượng", "Giá trị", "Nguồn"),
       ("Thời lượng log / số mẫu vị trí EKF2", "324,6 s / 40 544 mẫu (124,9 Hz)", "vehicle_local_position"),
       ("Số mẫu điểm đặt", "3 237", "vehicle_local_position_setpoint"),
       ("Thời gian ở OFFBOARD", "20,3 s (từ giây 296,0 tới 316,2)", "vehicle_status.nav_state"),
       ("Độ cao lớn nhất", "2,025 m (thiết kế 2,0 m)", "vehicle_local_position.z"),
       ("Sai số tới điểm mốc cuối mỗi đoạn giữ 5 s", "59,8 / 31,9 / 6,0 / 10,8 cm (TB 27,2 cm)", "So với 4 điểm mốc"),
       ("Mất gói kênh GCS (QGC, instance 0)", "0 gói / 357 bản tin nhận", "telemetry_status"),
       ("Mất gói kênh ứng dụng (instance 1)", "254 tính một lần lúc kết nối, sau đó 0", "telemetry_status"),
       ("Khoảng trống số thứ tự MAVLink tại cổng 14540", "0 / 484 khung trong 30 s", "Đếm số thứ tự MAVLink tại máy thu")],
      "Số liệu chuyến bay PX4 SITL", widths=[6.0, 5.6, 4.4])
    P("Hai điểm đầu có sai số lớn (59,8 và 31,9 cm) vì mỗi bước nhảy điểm đặt là 2 m và bộ điều khiển vị trí của PX4 "
      "vượt lố rồi dao động tắt dần (Hình 16b); 5 s chưa đủ để ổn định hoàn toàn. Hai điểm sau đạt 6–11 cm. Số 254 bản "
      "tin mất của instance 1 xuất hiện một lần duy nhất tại giây 294,9, đúng lúc kịch bản mở kết nối mới: PX4 so số "
      "thứ tự đầu tiên của nguồn mới với số cũ nên tính ra một khoảng trống lớn, sau đó không tăng thêm. Đây là hiện "
      "tượng đếm khi đổi nguồn, không phải mất gói thật. Hình 17 là bộ đếm của kênh GCS đọc bằng px4-listener.")
    F(EV / "hinh18_px4_listener_telemetry_status.png", "Bộ đếm telemetry_status của kênh MAVLink tới QGroundControl", width_cm=10.5)

    H("6.3. TN-1: Mở rộng quy mô đàn", 2)
    rows = [("N", "σ_{start} baseline (ms)", "σ_{start} đề xuất (ms)", "B baseline (byte/s)", "B đề xuất (byte/s)", "η = B_{b}/B_{p}")]
    for r in R["tn1"]:
        rows.append((r["N"], ms(r["base_skew_ms"], 3), ms(r["prop_skew_ms"], 3), f(r["base_bw_Bps"]["mean"], 0),
                     f(r["prop_bw_Bps"]["mean"], 1), f(r["base_bw_Bps"]["mean"] / r["prop_bw_Bps"]["mean"], 1)))
    T(rows, "Độ lệch khởi động và băng thông theo quy mô đàn (mạng không trễ, 3 lần lặp)",
      widths=[1.2, 3.4, 3.4, 2.9, 2.7, 2.4], align=[C] * 6)
    F(EV / "hinh_skew_vs_n.png", "Độ lệch khởi động theo quy mô đàn", width_cm=13.5)
    F(EV / "hinh_bandwidth_vs_n.png", "Băng thông chiều xuống theo quy mô đàn (thang log)", width_cm=13.5)
    t100 = R["tn1"][-1]
    P(f"**Băng thông (P2).** Baseline đo được {f(t100['base_bw_Bps']['mean'] / 100, 1)} byte/s cho mỗi drone, tăng đúng "
      f"tuyến tính tới {f(t100['base_bw_Bps']['mean'], 0)} byte/s tại N = 100 (lý thuyết 410N; đo thấp hơn 3 % vì trong "
      f"cửa sổ đo 3 s chu kỳ phát đầu tiên bắt đầu ở mốc 100 ms, nên mỗi drone nhận 29 thay vì 30 điểm đặt). Hệ đề xuất giữ khoảng 80 byte/s ở mọi N: 64 byte/s heartbeat như (4.10) cộng các "
      f"khung trigger 24 byte phát lặp trong cửa sổ quanh T_{{target}}. Tại N = 100, hệ số giảm băng thông là "
      f"{f(t100['base_bw_Bps']['mean'] / t100['prop_bw_Bps']['mean'], 0)} lần, khớp bậc với 6,4N = 640 trong (4.11).")
    P(f"**Độ lệch khởi động (P1).** Trên localhost không trễ, σ_{{start}} của baseline tăng tuyến tính từ "
      f"{f(R['tn1'][0]['base_skew_ms']['mean'], 3)} ms (N = 2) lên {f(t100['base_skew_ms']['mean'], 2)} ms (N = 100), "
      f"tức khoảng 20 µs cho mỗi lần `send` tuần tự, đúng dạng (N − 1)·τ_{{tx}} của (4.9). Hệ đề xuất cũng tăng nhẹ, tới "
      f"{f(t100['prop_skew_ms']['mean'], 2)} ms, nhưng nguyên nhân khác: 100 tiến trình cùng thức dậy một lúc trên 16 "
      "luồng phần cứng nên bộ lập lịch phải đánh thức lần lượt (thành phần w_{i} trong (4.8)). Trên drone thật mỗi agent có "
      "CPU riêng nên thành phần này không tồn tại. Ở mạng không trễ, cả hai đều rất nhỏ so với ngưỡng 25 ms; khác biệt "
      "thật sự xuất hiện khi mạng có trễ (Mục 6.4).")
    rows = [("N", "CPU GCS baseline (%)", "CPU GCS đề xuất (%)", "Tỷ lệ")]
    for r in R["tn1"]:
        rows.append((r["N"], ms(r["base_cpu_pct"], 2), ms(r["prop_cpu_pct"], 2),
                     f(r["base_cpu_pct"]["mean"] / r["prop_cpu_pct"]["mean"], 1)))
    T(rows, "Tải CPU của GCS theo quy mô đàn", widths=[1.6, 5.2, 5.2, 4.0], align=[C] * 4)
    P(f"GCS baseline tốn {f(t100['base_cpu_pct']['mean'], 2)} % một lõi tại N = 100 vì mỗi chu kỳ 100 ms phải gọi `send` "
      f"100 lần; GCS đề xuất tốn {f(t100['prop_cpu_pct']['mean'], 2)} %, phần lớn là phục vụ 100 kết nối TCP và 800 yêu "
      "cầu đồng bộ trong pha chuẩn bị.")

    H("6.4. TN-2: Ảnh hưởng của trễ mạng", 2)
    rows = [("Trễ TB một chiều (ms)", "σ_{start} baseline (ms)", "σ_{start} đề xuất (ms)", "|θ̂ − θ| (ms)", "ε = R_{min}/2 (ms)")]
    for r in R["tn2"]:
        rows.append((r["jitter_ms"], ms(r["base_skew_ms"]), ms(r["prop_skew_ms"]), ms(r["prop_abs_clock_err_ms"]),
                     ms(r["prop_eps_ms"])))
    T(rows, "Độ lệch khởi động và sai số đồng bộ theo trễ mạng (N = 20, 3 lần lặp)",
      widths=[2.8, 3.4, 3.4, 3.2, 3.2], align=[C] * 5)
    F(EV / "hinh_skew_vs_jitter.png", "Độ lệch khởi động theo trễ hàng đợi trung bình", width_cm=13.5)
    t20 = R["tn2"][-1]
    total = sum(len(r["prop_abs_clock_err_ms"]["values"]) for r in R["tn2"])
    P(f"Khi trễ trung bình tăng từ 0 lên 20 ms, σ_{{start}} của baseline tăng từ {f(R['tn2'][0]['base_skew_ms']['mean'])} lên "
      f"{f(t20['base_skew_ms']['mean'], 1)} ms: lệnh bắt đầu đến mỗi drone sau một trễ ngẫu nhiên khác nhau, và hiệu "
      "giữa trễ lớn nhất và nhỏ nhất của 20 đường truyền rơi thẳng vào σ_{start} (số hạng max d_i − min d_i trong (4.9)). "
      f"Từ trễ 5 ms trở lên, baseline vượt ngưỡng 25 ms hoặc ở sát ngưỡng. Hệ đề xuất chỉ lên {f(t20['prop_skew_ms']['mean'], 1)} "
      f"ms, nhỏ hơn {f(t20['base_skew_ms']['mean'] / t20['prop_skew_ms']['mean'], 1)} lần, vì trễ của gói trigger không "
      "ảnh hưởng thời điểm bắt đầu; chỉ còn sai số đồng bộ, mà sai số này nhỏ hơn trễ nhiều nhờ bộ lọc.")
    P(f"**Kiểm chứng cận sai số (P4).** Trong cả {total} lần đồng bộ của TN-2, không lần nào |θ̂ − θ| vượt ε = R_{{min}}/2: "
      "cận (4.6) đúng 100 %. Trung bình sai số thực chỉ bằng khoảng một nửa cận. Ở trễ 0, hệ đề xuất có σ_{start} "
      f"{f(R['tn2'][0]['prop_skew_ms']['mean'])} ms, lớn hơn baseline, vì lúc này sai số đồng bộ gần như bằng 0 và phần "
      "còn lại là độ trễ đánh thức tiến trình của hệ điều hành.")

    H("6.5. TN-3: Ảnh hưởng của mất gói", 2)
    rows = [("p (%)", "E_{RMS} baseline đo (cm)", "E_{RMS} lý thuyết (4.14) (cm)", "max e baseline (cm)",
             "E_{RMS} đề xuất (cm)", "Drone đề xuất khởi động")]
    for r in R["tn3"]:
        rows.append((r["p_loss"], ms(r["base_e_rms_cm"]), f(r["theory_rms_cm"]), f(r["base_e_max_cm"], 0),
                     f(r["prop_e_rms_cm"], 4), f"{r['prop_started']}/{r['prop_total']}"))
    T(rows, "Sai số vị trí theo tỷ lệ mất gói (N = 20, v = 2 m/s, 5 lần lặp)",
      widths=[1.3, 3.2, 3.0, 2.6, 2.8, 3.1], align=[C] * 6)
    F(EV / "hinh_error_vs_loss.png", "Sai số vị trí E_RMS theo tỷ lệ mất gói", width_cm=13.5)
    t3 = R["tn3"]
    P("**Baseline khớp mô hình (P3).** E_{RMS} đo được bám sát (4.14): sai khác so với lý thuyết dưới 5 % ở cả bốn mức "
      f"p > 0 ({f(t3[1]['base_e_rms_cm']['mean'])} so với {f(t3[1]['theory_rms_cm'])} cm ở p = 1 %, "
      f"{f(t3[4]['base_e_rms_cm']['mean'])} so với {f(t3[4]['theory_rms_cm'])} cm ở p = 20 %). Sai số cực đại lên "
      f"{f(t3[3]['base_e_max_cm'], 0)} cm ở p ≥ 10 %, ứng với chuỗi 4 gói mất liên tiếp. Nếu hai drone cạnh nhau cùng gặp "
      "điều này theo hai hướng ngược nhau, khoảng cách giữa chúng thay đổi 1,6 m, đủ để vi phạm d_{safe} của nhiều đội hình "
      "dày.")
    P(f"**Hệ đề xuất không phụ thuộc p.** E_{{RMS}} giữ ở mức 10⁻⁴ cm ở mọi p: sai số chỉ còn v·|θ̂ − θ| với sai số đồng bộ "
      f"cỡ µs trên localhost. Ở p = 20 %, mỗi agent mất trung bình {f(t3[4]['prop_heartbeats_lost'] / t3[4]['prop_total'], 1)} "
      "heartbeat nhưng cả 100/100 lần chạy vẫn khởi động đúng (trigger được phát lặp nên ít nhất một bản đến nơi) và "
      "không lần nào failsafe kích hoạt nhầm (cần mất 8 heartbeat liên tiếp).")
    P("Phép so sánh trên đo ở mức **điểm đặt**, chưa qua động lực học bay; sai số bám của bộ điều khiển PX4 "
      "(Bảng 18) cộng thêm như nhau cho cả hai kiến trúc.")

    H("6.6. TN-4: Hiệu quả bộ lọc chọn mẫu", 2)
    stats = {}
    for jit, per_k in R["tn4"].items():
        for k, d in per_k.items():
            stats[(jit, k)] = {m: (statistics.fmean(abs(x) for x in v), statistics.stdev(v)) for m, v in d.items()}
    rows = [("K", "Trễ 1 ms: trung bình", "Trễ 1 ms: RTT nhỏ nhất", "Trễ 5 ms: trung bình", "Trễ 5 ms: RTT nhỏ nhất")]
    for k in ("1", "2", "4", "8", "16"):
        rows.append((k, *[f"{f(stats[(j, k)][m][0], 3)} ({f(stats[(j, k)][m][1], 3)})"
                          for j in ("1", "5") for m in ("mean", "min_rtt")]))
    T(rows, "Sai số |θ̂ − θ| trung bình (độ lệch chuẩn), ms, theo số mẫu K và cách chọn (100 agent mỗi ô)",
      widths=[1.2, 3.7, 3.7, 3.7, 3.7], align=[C] * 5)
    F(EV / "hinh_clock_filter.png", "Phân bố sai số ước lượng đồng hồ theo K, trễ trung bình 5 ms", width_cm=13.5)
    a, b = stats[("5", "16")]["min_rtt"][0], stats[("5", "16")]["mean"][0]
    P(f"Ở trễ 5 ms, sai số trung bình giảm từ {f(stats[('5', '1')]['min_rtt'][0])} ms với một mẫu xuống "
      f"{f(a)} ms với 16 mẫu khi chọn mẫu RTT nhỏ nhất, tức gần 5 lần. Cùng 16 mẫu, lấy trung bình chỉ đạt {f(b)} ms, "
      f"kém {f(b / a, 1)} lần. Ở trễ 1 ms, khoảng cách hai cách nhỏ hơn vì trễ ít biến động. Kết quả xác nhận lập luận ở "
      "Mục 4.3.3: bộ lọc RTT nhỏ nhất loại hẳn mẫu bị trễ đột biến, còn trung bình chỉ làm loãng. K = 8 (cấu hình mặc "
      "định) là điểm cân bằng: sai số đã giảm hơn 3 lần so với K = 1, thời gian đồng bộ khoảng 0,1 s ở trễ 5 ms.")

    H("6.7. TN-5: Cơ chế failsafe khi GCS ngừng hoạt động", 2)
    d = [x for r in R["tn5"] for x in r["delay_ms"]]
    det = sum(r["detected"] for r in R["tn5"])
    tot = sum(r["n"] for r in R["tn5"])
    T([("Chỉ tiêu", "Kết quả đo", "Thiết kế"),
       ("Số agent chuyển FAILSAFE", f"{det}/{tot}", "100 %"),
       ("Thời gian từ lúc tắt GCS tới FAILSAFE", f"{f(min(d), 1)} – {f(max(d), 1)} ms", "≤ 2000 ms + chu kỳ poll"),
       ("Chênh lệch giữa các agent trong một lần", f"≤ {f(max(max(r['delay_ms']) - min(r['delay_ms']) for r in R['tn5']), 2)} ms", "–"),
       ("Lệnh an toàn phát ra", "MAV_CMD_DO_SET_MODE: AUTO_HOVER", "AUTO_HOVER")],
      "Kết quả kiểm chứng failsafe (N = 10, 3 lần)", widths=[6.4, 5.4, 4.2])
    P("GCS bị tắt đột ngột bằng SIGKILL khi đàn đang bay. Cả 30 agent phát hiện mất liên lạc và chuyển AUTO_HOVER. Thời "
      "gian đo được hơi dưới 2000 ms vì đồng hồ timeout tính từ heartbeat cuối cùng nhận được, mà heartbeat đó đến trước "
      "lúc tắt GCS khoảng 25 ms. Mười agent phát hiện gần như cùng lúc vì chúng cùng nhận một heartbeat multicast cuối.")

    H("6.8. Tổng hợp so sánh", 2)
    j20 = R["tn2"][-1]
    p10 = R["tn3"][3]
    T([("Chỉ số", "Điều kiện", "Baseline", "Đề xuất", "Nhận xét"),
       ("Băng thông khi bay", "N = 100", f"{f(t100['base_bw_Bps']['mean'], 0)} B/s", f"{f(t100['prop_bw_Bps']['mean'], 1)} B/s",
        f"Giảm {f(t100['base_bw_Bps']['mean'] / t100['prop_bw_Bps']['mean'], 0)} lần"),
       ("σ_{start}", "N = 100, không trễ", f"{f(t100['base_skew_ms']['mean'])} ms", f"{f(t100['prop_skew_ms']['mean'])} ms",
        "Cả hai ≪ 25 ms"),
       ("σ_{start}", "N = 20, trễ TB 20 ms", f"{f(j20['base_skew_ms']['mean'], 1)} ms", f"{f(j20['prop_skew_ms']['mean'], 1)} ms",
        f"Nhỏ hơn {f(j20['base_skew_ms']['mean'] / j20['prop_skew_ms']['mean'], 1)} lần"),
       ("E_{RMS}", "p = 10 %", f"{f(p10['base_e_rms_cm']['mean'])} cm", f"{f(p10['prop_e_rms_cm'], 4)} cm", "Không phụ thuộc p"),
       ("max e", "p = 10 %", f"{f(p10['base_e_max_cm'], 0)} cm", f"{f(p10['prop_e_max_cm'], 4)} cm", ""),
       ("CPU GCS", "N = 100", f"{f(t100['base_cpu_pct']['mean'])} %", f"{f(t100['prop_cpu_pct']['mean'])} %",
        f"Giảm {f(t100['base_cpu_pct']['mean'] / t100['prop_cpu_pct']['mean'], 1)} lần"),
       ("GCS ngừng", "Khi đang bay", "Đứng ở điểm đặt cuối", "AUTO_HOVER sau ~2 s", "30/30 agent")],
      "Tổng hợp so sánh hai kiến trúc", widths=[2.6, 3.4, 3.3, 3.3, 3.4], align=[L, L, C, C, L])
    H("6.9. Bàn luận", 2)
    B(["**Mức khớp giữa mô hình và đo đạc.** P2 (băng thông) và P3 (sai số khi mất gói) khớp định lượng trong vòng vài "
       "phần trăm. P4 (cận sai số) đúng trên 100 % mẫu. P1 khớp về dạng (baseline tuyến tính theo N và cộng toàn bộ "
       "biến thiên trễ), nhưng trên một máy, thành phần đánh thức tiến trình làm hệ đề xuất không đạt σ_{start} thấp như "
       "lý thuyết khi N lớn và mạng không trễ.",
       "**Đánh đổi của hệ đề xuất.** Agent cần bộ nhớ chứa quỹ đạo, GCS phải nạp xong mới phát trigger, và muốn đổi "
       "kịch bản giữa chừng phải dừng rồi nạp lại. Đổi lại, trong lúc bay hệ thống gần như không phụ thuộc mạng.",
       "**Giả thiết kênh đối xứng.** Ước lượng (4.5) lệch Δ/2 khi kênh bất đối xứng; nhưng cận (4.6) vẫn đúng và mỗi "
       "drone tự biết ε của mình, nên có thể từ chối bay nếu ε lớn hơn ngưỡng.",
       "**Mạng vô tuyến thật.** Multicast trên Wi-Fi phát ở tốc độ cơ sở và không có ACK tầng liên kết, nên tỷ lệ mất "
       "gói multicast cao hơn unicast; thiết kế đã bù bằng cách phát lặp trigger và cho phép mất tới 7 heartbeat liên tiếp. "
       "Mất gói theo cụm (mô hình Gilbert–Elliott [17]) còn làm baseline xấu hơn vì sai số tăng theo độ dài chuỗi mất."])


# ============================================================ 7
def ch7():
    H("7. Kết luận và hướng phát triển", 1)
    H("7.1. Kết quả đạt được", 2)
    t100, j20, p10 = R["tn1"][-1], R["tn2"][-1], R["tn3"][3]
    B([f"Hiện thực bằng C trên POSIX socket một hệ điều phối 100 drone gồm GCS dùng epoll, giao thức nhị phân DLSP "
       "(header 16 byte, CRC-16, big-endian), đồng bộ Cristian có lọc, kích hoạt bằng một gói multicast và failsafe phân tán.",
       "Hiện thực hệ tham chiếu unicast streaming dùng chung bộ mã giao thức và khung đo tự động cho 5 nhóm thực nghiệm.",
       f"Đo được: băng thông khi bay giảm {f(t100['base_bw_Bps']['mean'] / t100['prop_bw_Bps']['mean'], 0)} lần tại N = 100; "
       f"độ lệch khởi động dưới trễ 20 ms nhỏ hơn {f(j20['base_skew_ms']['mean'] / j20['prop_skew_ms']['mean'], 1)} lần; "
       f"sai số vị trí khi mất 10 % gói từ {f(p10['base_e_rms_cm']['mean'])} cm xuống mức không đáng kể; 30/30 agent "
       "failsafe đúng khi GCS ngừng.",
       "Kiểm chứng tầng MAVLink với PX4 v1.14.4 SITL: OFFBOARD, ARM, bay 4 điểm mốc ở độ cao 2 m, hạ cánh; phân tích "
       "ULog và bộ đếm telemetry_status."])
    H("7.2. Mức độ hoàn thành", 2)
    T([("Mục tiêu (Mục 2.4)", "Mức độ", "Ghi chú"),
       ("Kiến trúc tách kênh dữ liệu và thời gian", "Hoàn thành", "TCP nạp trước, multicast kích hoạt, agent chạy theo đồng hồ"),
       ("Giao thức nhị phân DLSP", "Hoàn thành", "9 loại bản tin, kiểm thử đơn vị phủ 100 % protocol.c"),
       ("Đồng bộ Cristian và failsafe", "Hoàn thành", "Cận sai số đúng 100 %, failsafe 30/30"),
       ("Hệ tham chiếu và khung đánh giá", "Hoàn thành", "TN-1 đến TN-5, số liệu tái lập bằng một lệnh"),
       ("Tích hợp PX4 SITL", "Một phần", "Bay thử 1 drone bằng kịch bản riêng; agent C chưa gửi MAVLink trực tiếp"),
       ("Quỹ đạo nhiều điểm, hiển thị 3D", "Chưa", "Định dạng hỗ trợ M điểm nhưng bộ sinh hiện chỉ tạo 1 điểm/drone")],
      "Mức độ hoàn thành mục tiêu", widths=[5.4, 2.4, 8.2])
    H("7.3. Hạn chế", 2)
    B(["Mọi thử nghiệm chạy trên một máy qua loopback; trễ, mất gói và lệch đồng hồ được giả lập ở tầng ứng dụng, chưa "
       "đo trên mạng Wi-Fi thật hay bằng tc netem.",
       "Chỉ một drone chạy PX4 SITL; sai số vị trí của TN-3 đo ở mức điểm đặt, chưa qua động lực học bay.",
       "Agent C chưa có cầu nối MAVLink: phần bay PX4 do kịch bản Python thực hiện độc lập.",
       "Đồng bộ chỉ thực hiện một lần trước khi bay; buổi diễn dài hơn khoảng 100 s cần đồng bộ lại để bù trôi tần số.",
       "Giao thức chưa xác thực nguồn gửi: bất kỳ máy nào trong nhóm multicast cũng có thể gửi trigger hoặc lệnh dừng."])
    H("7.4. Hướng phát triển", 2)
    B(["Thêm cầu nối MAVLink vào agent C (UDP tới 14580 + i), chạy 3–5 phiên PX4 SITL để đo sai số bám thực tế khi mất gói.",
       "Đồng bộ lại định kỳ dựa trên heartbeat mang mốc thời gian chủ; hoặc dùng PTP (IEEE 1588 [11]) khi phần cứng hỗ trợ.",
       "Thêm mã xác thực thông điệp (HMAC) cho trigger và lệnh dừng khẩn.",
       "Chạy lại ma trận thực nghiệm trên nhiều máy qua Wi-Fi thật và với tc netem theo mô hình mất gói cụm.",
       "Bộ sinh quỹ đạo nhiều điểm có kiểm tra khoảng cách an toàn và bộ hiển thị 3D cho toàn đàn."])


def refs():
    H("Tài liệu tham khảo", 1)
    items = [
        'PX4 Development Team, "PX4 Autopilot User Guide (v1.14)." [Trực tuyến]. Địa chỉ: https://docs.px4.io/v1.14/en/. Truy cập: 11/2026.',
        'PX4 Development Team, "Simulation: Software In The Loop." [Trực tuyến]. Địa chỉ: https://docs.px4.io/v1.14/en/simulation/. Truy cập: 11/2026.',
        'MAVLink Development Team, "MAVLink Developer Guide." [Trực tuyến]. Địa chỉ: https://mavlink.io/en/. Truy cập: 11/2026.',
        'F. Cristian, "Probabilistic clock synchronization," Distributed Computing, vol. 3, no. 3, pp. 146–158, 1989.',
        'D. L. Mills, "Internet time synchronization: The network time protocol," IEEE Trans. Commun., vol. 39, no. 10, pp. 1482–1493, 1991.',
        'S. Deering, "Host extensions for IP multicasting," RFC 1112, IETF, 1989.',
        'W. R. Stevens, B. Fenner, A. M. Rudoff, UNIX Network Programming, Vol. 1: The Sockets Networking API, 3rd ed. Addison-Wesley, 2003.',
        'J. F. Kurose, K. W. Ross, Computer Networking: A Top-Down Approach, 8th ed. Pearson, 2021.',
        'M. van Steen, A. S. Tanenbaum, Distributed Systems, 3rd ed. distributed-systems.net, 2017.',
        'M. Kerrisk, "epoll(7) — Linux manual page." [Trực tuyến]. Địa chỉ: https://man7.org/linux/man-pages/man7/epoll.7.html.',
        'IEEE Std 1588-2019, "IEEE Standard for a Precision Clock Synchronization Protocol for Networked Measurement and Control Systems," 2020.',
        'Linux Foundation, "tc-netem(8) — Network Emulator." [Trực tuyến]. Địa chỉ: https://man7.org/linux/man-pages/man8/tc-netem.8.html.',
        'G. Cook, "Catalogue of parametrised CRC algorithms: CRC-16/IBM-3740 (CCITT-FALSE)." [Trực tuyến]. Địa chỉ: https://reveng.sourceforge.io/crc-catalogue/16.htm.',
        'PX4, "pyulog: Python module for ULog files." [Trực tuyến]. Địa chỉ: https://github.com/PX4/pyulog.',
        'Dronecode, "QGroundControl User Guide." [Trực tuyến]. Địa chỉ: https://docs.qgroundcontrol.com/.',
        'L. T. Trà, T. Đ. Tín, N. X. Trường, "Mô phỏng và điều khiển USV trên nền tảng PX4 và MAVLink," Báo cáo cuối kỳ Lập trình mạng, Trường ĐH Bách khoa – ĐH Đà Nẵng, 11/2025.',
        'E. N. Gilbert, "Capacity of a burst-noise channel," Bell Syst. Tech. J., vol. 39, no. 5, pp. 1253–1265, 1960.']
    for i, text in enumerate(items, 1):
        p = rep.doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(1.0)
        p.paragraph_format.first_line_indent = Cm(-1.0)
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.alignment = L
        p.add_run(f"[{i}]\t{text}")


def appendix():
    H("Phụ lục. Tái lập kết quả", 1)
    P("Các lệnh dưới đây chạy từ thư mục gốc dự án, tái tạo toàn bộ số liệu và hình trong báo cáo.")
    T([("Bước", "Lệnh", "Kết quả"),
       ("Biên dịch, kiểm thử", "make clean && make && make test", "bin/, Hình 11"),
       ("Ma trận thực nghiệm (~15 phút)", "python3 -I scripts/evaluate_baseline.py", "evidence/results.json"),
       ("Biểu đồ", "python3 -I scripts/plot_results.py", "evidence/hinh_*.png"),
       ("Khung tin", "python3 -I scripts/capture_frames.py", "evidence/frames.json"),
       ("Sơ đồ, lưu đồ", "python3 -I scripts/draw_diagrams.py", "evidence/diagrams/"),
       ("Phân tích ULog", "~/px4-venv/bin/python -I scripts/plot_ulog.py", "evidence/hinh_ulog_flight.png"),
       ("Bay thử SITL", "~/px4-venv/bin/python -I scripts/sitl_flight.py --execute-sitl", "Chỉ chạy với PX4 SITL cục bộ"),
       ("Báo cáo", "python3 -I tools/build_report.py", "docs/BAO_CAO_DRONE_LIGHT_SHOW.docx")],
      "Lệnh tái lập", widths=[3.6, 8.2, 4.2], mono_cols=(1,))


def main():
    cover()
    front_matter()
    rep.body_section()
    for chapter in (ch1, ch2, ch3, ch4, ch5, ch6, ch7):
        chapter()
    rep.page_break()
    refs()
    rep.page_break()
    appendix()
    rep.save(OUT)
    print(f"saved {OUT}  figures={rep.counts['Hình']} tables={rep.counts['Bảng']}")


if __name__ == "__main__":
    main()
