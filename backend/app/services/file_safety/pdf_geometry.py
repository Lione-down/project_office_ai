def pdf_text_bbox(
    text: str,
    current_matrix,
    text_matrix,
    font_size,
) -> tuple[float, float, float, float]:
    height = max(float(font_size or 0), 1.0)
    width = max(len(text) * height * 0.5, 1.0)
    points = [
        _transform_point(x, y, text_matrix, current_matrix)
        for x, y in ((0.0, 0.0), (width, 0.0), (width, height), (0.0, height))
    ]
    x_values = [point[0] for point in points]
    y_values = [point[1] for point in points]
    return min(x_values), min(y_values), max(x_values), max(y_values)


def _transform_point(
    x: float,
    y: float,
    text_matrix,
    current_matrix,
) -> tuple[float, float]:
    text_x = text_matrix[0] * x + text_matrix[2] * y + text_matrix[4]
    text_y = text_matrix[1] * x + text_matrix[3] * y + text_matrix[5]
    return (
        float(
            current_matrix[0] * text_x + current_matrix[2] * text_y + current_matrix[4]
        ),
        float(
            current_matrix[1] * text_x + current_matrix[3] * text_y + current_matrix[5]
        ),
    )
