def calculate_severity(box, conf, img_shape):
    x1, y1, x2, y2 = box.xyxy[0]
    area = (x2 - x1) * (y2 - y1)
    total = img_shape[0] * img_shape[1]
    ratio = area / total

    if ratio > 0.15 or conf > 0.8:
        return "High"
    elif ratio > 0.05:
        return "Medium"
    return "Low"