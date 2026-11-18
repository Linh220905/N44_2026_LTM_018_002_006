#include "geofence.h"
#include <stddef.h>
#include <math.h>

void geofence_box_init(geofence_box_t *box,
                       double min_x, double max_x,
                       double min_y, double max_y,
                       double min_z, double max_z) {
    if (!box) return;

    box->min_x = min_x;
    box->max_x = max_x;
    box->min_y = min_y;
    box->max_y = max_y;
    box->min_z = min_z;
    box->max_z = max_z;
}

bool geofence_is_breached(const geofence_box_t *box, double x, double y, double z) {
    // Nếu không cấu hình Geofence (NULL), coi là vi phạm an toàn để dừng khẩn cấp
    if (box == NULL || !isfinite(x) || !isfinite(y) || !isfinite(z) ||
        !isfinite(box->min_x) || !isfinite(box->max_x) ||
        !isfinite(box->min_y) || !isfinite(box->max_y) ||
        !isfinite(box->min_z) || !isfinite(box->max_z) ||
        box->min_x > box->max_x || box->min_y > box->max_y || box->min_z > box->max_z) {
        return true;
    }

    // Kiểm tra trục X (North)
    if (x < box->min_x || x > box->max_x) {
        return true;
    }

    // Kiểm tra trục Y (East)
    if (y < box->min_y || y > box->max_y) {
        return true;
    }

    // Kiểm tra trục Z (Down trong hệ NED: z âm là độ cao dương)
    // Nếu drone bay cao hơn trần trần cho phép (z < min_z) hoặc chìm sâu hơn sàn (z > max_z)
    if (z < box->min_z || z > box->max_z) {
        return true;
    }

    return false;
}
