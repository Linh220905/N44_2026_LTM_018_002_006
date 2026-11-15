#ifndef GEOFENCE_H
#define GEOFENCE_H

#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Cấu trúc định nghĩa hộp không gian an toàn 3D (Bounding Box) theo hệ tọa độ NED (North-East-Down).
 * 
 * Lưu ý hệ tọa độ NED:
 * - x: Trục Bắc (North, mét), giá trị dương hướng Bắc.
 * - y: Trục Đông (East, mét), giá trị dương hướng Đông.
 * - z: Trục Xuống (Down, mét), giá trị âm biểu thị độ cao dương so với mặt đất (VD: cao 30m -> z = -30.0).
 */
typedef struct {
    double min_x, max_x;
    double min_y, max_y;
    double min_z, max_z; // Chú ý hệ NED: z âm là độ cao dương
} geofence_box_t;

/**
 * @brief Khởi tạo cấu trúc geofence_box_t với các biên xác định.
 * 
 * @param box Con trỏ tới geofence_box_t cần khởi tạo.
 * @param min_x Biên dưới trục X (North).
 * @param max_x Biên trên trục X (North).
 * @param min_y Biên dưới trục Y (East).
 * @param max_y Biên trên trục Y (East).
 * @param min_z Biên dưới trục Z (Down, độ cao tối đa đạt được sẽ là giá trị âm nhỏ nhất).
 * @param max_z Biên trên trục Z (Down, mặt đất/giới hạn dưới).
 */
void geofence_box_init(geofence_box_t *box,
                       double min_x, double max_x,
                       double min_y, double max_y,
                       double min_z, double max_z);

/**
 * @brief Kiểm tra xem tọa độ (x, y, z) có vượt ra ngoài vùng không gian an toàn hay không.
 * 
 * @param box Con trỏ tới hộp geofence.
 * @param x Tọa độ hiện tại trục X (North, mét).
 * @param y Tọa độ hiện tại trục Y (East, mét).
 * @param z Tọa độ hiện tại trục Z (Down, mét).
 * @return true nếu tọa độ nằm ngoài hộp an toàn (vi phạm geofence) hoặc box == NULL.
 * @return false nếu tọa độ nằm an toàn bên trong hộp (bao gồm cả biên).
 */
bool geofence_is_breached(const geofence_box_t *box, double x, double y, double z);

#ifdef __cplusplus
}
#endif

#endif // GEOFENCE_H
