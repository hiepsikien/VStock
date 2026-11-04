# Cửa Compass — giai đoạn chọn

Số liệu kéo ngày 2026-10-12. Chỉ giai đoạn 2021-01-04 → 2024-12-31.
Giai đoạn xác nhận chưa chạy. Kết quả dưới đây không đổi `Được vào`.

## Luật đã khóa trước khi đọc spread

- Đích hồi quy: biên lợi nhuận gộp quý này trừ quý liền trước. Tử là khoản 23100, mẫu là khoản 21001, cùng đơn vị tiền.
- Quý được nhìn sau 45 ngày kể từ ngày kết thúc quý. β cửa sổ mở rộng, tối thiểu 12 cặp. Thiếu thì mã rời ngày đó.
- Vế phải và cú sốc ngày: lợi suất 60 phiên của CL=F, biết đến hết phiên đang xét.
- Mua giá đóng cửa phiên sau tín hiệu, giữ 60 phiên. Sự kiện là lần cắt ngưỡng, không lấy phiên đang đứng sẵn trên ngưỡng.
- Dấu viết tay: PVD +, GAS +, DCM −, DPM −. NT2 đứng ngoài cả ba spread.
- β giá: OLS lợi suất ngày, 756 phiên chung, chỉ phiên trước ngày tín hiệu.
- Ngưỡng là mức lớn nhất trong lưới 0.10, 0.12, 0.15, 0.18, 0.20, 0.25 còn ít nhất 8 sự kiện dầu. Lưới không được nới sau bước này.
- Chấm khi còn ít nhất 8 sự kiện mà cả ba cách chia phía đều đủ hai mã. Spread là trung bình lợi suất phía dương trừ phía âm. Cửa thắng là trung bình spread của Z dương, lớn hơn dấu viết tay, và lớn hơn β giá.
- Lợi suất tới của một sự kiện mở trong giai đoạn chọn có thể kết thúc sau 2024-12-31. Đó vẫn là kết quả của sự kiện đã mở, không phải một sự kiện của giai đoạn xác nhận.

## Đối chiếu biên gộp

Khoản 23100 / 21001 khớp `GROSS_MARGIN_QR` của quý mới nhất từng mã, sai số dưới 0,01 điểm phần trăm.

## Ngưỡng dầu

Ngưỡng khóa ở 0.25. Sự kiện dầu trong giai đoạn chọn: 8. Lịch chung của bốn mã: 2881 phiên.
Cặp biên gộp dùng được: PVD 50 cặp, GAS 50 cặp, DCM 45 cặp, DPM 50 cặp.

## Kết quả

Chưa đủ sự kiện để chấm. Sự kiện chấm được: 0. Sự kiện dầu bị loại: 8.

- Spread Z: —
- Spread dấu viết tay: —
- Spread β giá: —

| Phiên | Dầu 60 phiên | PVD | GAS | DCM | DPM | Spread Z | Dấu viết tay | β giá |
|---|---:|---:|---:|---:|---:|---:|---:|---:|

Sự kiện dầu không vào trung bình:

- 2021-01-07: β giá không đủ hai mã mỗi phía (dấu Z PVD+ GAS+ DCM− DPM−; dấu điểm giá PVD− GAS+ DCM− DPM−)
- 2021-06-21: β giá không đủ hai mã mỗi phía (dấu Z PVD+ GAS+ DCM− DPM−; dấu điểm giá PVD− GAS+ DCM− DPM−)
- 2021-11-02: β giá không đủ hai mã mỗi phía (dấu Z PVD+ GAS+ DCM− DPM−; dấu điểm giá PVD− GAS+ DCM− DPM−)
- 2022-02-23: β giá không đủ hai mã mỗi phía (dấu Z PVD+ GAS+ DCM− DPM−; dấu điểm giá PVD− GAS+ DCM− DPM−)
- 2022-06-09: β giá không đủ hai mã mỗi phía (dấu Z PVD+ GAS+ DCM− DPM−; dấu điểm giá PVD− GAS+ DCM− DPM−)
- 2022-09-13: β giá không đủ hai mã mỗi phía (dấu Z PVD− GAS− DCM+ DPM+; dấu điểm giá PVD+ GAS− DCM+ DPM+)
- 2023-09-07: β giá không đủ hai mã mỗi phía (dấu Z PVD+ GAS+ DCM− DPM−; dấu điểm giá PVD+ GAS+ DCM+ DPM+)
- 2023-12-12: β giá không đủ hai mã mỗi phía (dấu Z PVD− GAS− DCM+ DPM+; dấu điểm giá PVD− GAS− DCM+ DPM−)

Dấu β trong bảng là hệ số biên gộp đang có hiệu lực tại phiên đó, không phải điểm Z. Điểm Z là hệ số này nhân với lợi suất dầu của phiên.
