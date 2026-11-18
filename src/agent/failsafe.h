#ifndef FAILSAFE_H
#define FAILSAFE_H

#include <stdint.h>
#include <stdbool.h>
#include "../common/geofence.h"

#ifdef __cplusplus
extern "C" {
#endif

#define DEFAULT_HEARTBEAT_TIMEOUT_US 1500000ULL // 1.5s = 1,500,000 us (tương đương 3 chu kỳ mất Heartbeat 2Hz)
#define BATTERY_LOW_THRESHOLD_PCT 10.0f        // Mức cảnh báo pin yếu dưới 10%
#define BATTERY_LOW_THRESHOLD_RATIO 0.10f      // Tỉ lệ pin yếu dưới 0.10

// Định nghĩa mã lệnh MAVLink khẩn cấp chuẩn
#define MAV_CMD_NAV_LAND 21
#define MAV_CMD_DO_SET_MODE 176

// Chế độ bay MAVLink thông dụng trong tình huống khẩn cấp
typedef enum {
    FLIGHT_MODE_MANUAL = 0,
    FLIGHT_MODE_AUTO_MISSION = 1,
    FLIGHT_MODE_AUTO_HOVER = 2, // Loiter / PosHold / Brake giữ vị trí
    FLIGHT_MODE_AUTO_LAND = 3   // Tự động hạ cánh
} failsafe_flight_mode_t;

/**
 * @brief Cấu trúc mô phỏng lệnh MAVLink khẩn cấp (COMMAND_LONG) được phát ra
 */
typedef struct {
    uint16_t command;           // Ví dụ: MAV_CMD_NAV_LAND (21) hoặc MAV_CMD_DO_SET_MODE (176)
    float param1;               // Tuỳ chọn cho command (VD: chế độ bay cho DO_SET_MODE)
    float param2;
    float param3;
    float param4;
    float param5;               // Tọa độ X (North / Lat)
    float param6;               // Tọa độ Y (East / Lon)
    float param7;               // Tọa độ Z (Down / Alt)
    char description[64];       // Mô tả lệnh MAVLink
} failsafe_mavlink_cmd_t;

/**
 * @brief Các nguyên nhân kích hoạt Failsafe an toàn
 */
typedef enum {
    FAILSAFE_NONE = 0,
    FAILSAFE_HEARTBEAT_TIMEOUT, // Mất tín hiệu GCS quá 3 chu kỳ (>1.5s)
    FAILSAFE_GEOFENCE_BREACH,   // Văng ra khỏi khu vực biểu diễn
    FAILSAFE_BATTERY_LOW,       // Điện áp pin < 10%
    FAILSAFE_EMERGENCY_TRIGGER  // Lệnh dừng khẩn cấp từ GCS
} failsafe_reason_t;

struct failsafe_monitor;
typedef void (*failsafe_action_callback_t)(struct failsafe_monitor *mon,
                                          const failsafe_mavlink_cmd_t *cmd,
                                          void *user_data);

/**
 * @brief Cấu trúc giám sát an toàn Failsafe cấp Agent trên drone
 */
typedef struct failsafe_monitor {
    uint64_t last_heartbeat_us;
    uint64_t timeout_us; // Mặc định 1,500,000 us (1.5s)
    geofence_box_t fence;
    float battery_remaining;
    bool is_triggered;
    failsafe_reason_t reason;

    // Trạng thái lệnh MAVLink khẩn cấp được sinh ra
    failsafe_mavlink_cmd_t last_emergency_cmd;
    failsafe_action_callback_t action_callback;
    void *callback_user_data;
} failsafe_monitor_t;

/**
 * @brief Khởi tạo module Failsafe
 * 
 * @param mon Con trỏ tới cấu trúc failsafe_monitor_t.
 * @param box Con trỏ tới vùng không gian geofence an toàn.
 */
void failsafe_init(failsafe_monitor_t *mon, const geofence_box_t *box);

/**
 * @brief Cập nhật thời điểm nhận gói Heartbeat gần nhất từ GCS
 * 
 * @param mon Con trỏ tới failsafe_monitor_t.
 * @param now_us Thời điểm hiện tại tính bằng micro giây (us).
 */
void failsafe_update_heartbeat(failsafe_monitor_t *mon, uint64_t now_us);

/**
 * @brief Cập nhật trạng thái dung lượng pin còn lại
 * 
 * @param mon Con trỏ tới failsafe_monitor_t.
 * @param battery_remaining Tỉ lệ pin còn lại (hỗ trợ cả thang 0.0 - 1.0 hoặc 0 - 100%).
 */
void failsafe_update_battery(failsafe_monitor_t *mon, float battery_remaining);

/**
 * @brief Kích hoạt ngắt khẩn cấp thủ công từ lệnh người điều khiển hoặc GCS
 * 
 * @param mon Con trỏ tới failsafe_monitor_t.
 */
void failsafe_trigger_emergency(failsafe_monitor_t *mon);

/**
 * @brief Đăng ký callback gửi lệnh MAVLink khẩn cấp ra bus phần cứng
 * 
 * @param mon Con trỏ tới failsafe_monitor_t.
 * @param cb Hàm callback xử lý gói tin MAVLink.
 * @param user_data Dữ liệu người dùng truyền vào callback.
 */
void failsafe_set_action_callback(failsafe_monitor_t *mon,
                                  failsafe_action_callback_t cb,
                                  void *user_data);

/**
 * @brief Kiểm tra toàn bộ điều kiện an toàn và kích hoạt Failsafe nếu có vi phạm
 * 
 * @param mon Con trỏ tới failsafe_monitor_t.
 * @param now_us Thời điểm hiện tại tính bằng micro giây (us).
 * @param x Tọa độ hiện tại North (m).
 * @param y Tọa độ hiện tại East (m).
 * @param z Tọa độ hiện tại Down (m, z < 0 là bay trên cao).
 * @return failsafe_reason_t Mã trạng thái Failsafe (FAILSAFE_NONE nếu bình thường).
 */
failsafe_reason_t failsafe_check(failsafe_monitor_t *mon, uint64_t now_us, double x, double y, double z);

/**
 * @brief Lấy chuỗi mô tả nguyên nhân Failsafe
 * 
 * @param reason Mã nguyên nhân.
 * @return const char* Chuỗi văn bản mô tả.
 */
const char *failsafe_reason_to_str(failsafe_reason_t reason);

#ifdef __cplusplus
}
#endif

#endif // FAILSAFE_H
