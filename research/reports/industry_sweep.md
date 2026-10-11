# Cổng ngành theo cửa sổ 14, 30, 60 phiên

Nến từ 2014-01-02 đến 2026-10-09, 106 mã.
Bảng sàn: 709 mã từ `backend/data/vstock.db`, 103/106 mã của rổ có sàn; OIL, QNS, ACV không có nên dùng biên độ rộng nhất.
Tin từ 2024-01-02, dòng ngoại từ 2018-08-30.

Cửa sổ là số phiên dùng để so lợi suất ngành với VN-Index, và cũng là cửa sổ của chuỗi dầu. Định nghĩa đợt tăng (66 phiên, +20%, cửa sớm dưới +15%), rổ theo năm, ngưỡng tín dụng và VN-Index trên MA200 giữ nguyên. Không có bước nào gọi mô hình ngôn ngữ.

## Tín hiệu

| Cửa sổ | Giai đoạn | Đợt | Recall | Precision ngành | Tỷ lệ nền | Precision / nền | Ngành mở TB |
|---|---|---|---|---|---|---|---|
| 14 | Lùi | 648 | 58.8% | 16.4% | 14.9% | 1.10 | 3.17 |
| 14 | Chọn | 560 | 61.1% | 17.4% | 14.3% | 1.22 | 4.07 |
| 14 | Xác nhận | 171 | 68.4% | 10.7% | 12.5% | 0.85 | 4.05 |
| 30 | Lùi | 648 | 55.9% | 16.3% | 14.9% | 1.10 | 3.16 |
| 30 | Chọn | 560 | 57.3% | 17.3% | 14.3% | 1.22 | 4.03 |
| 30 | Xác nhận | 171 | 60.2% | 10.4% | 12.5% | 0.83 | 3.91 |
| 60 | Lùi | 648 | 48.9% | 17.7% | 14.9% | 1.19 | 3.22 |
| 60 | Chọn | 560 | 59.1% | 18.1% | 14.3% | 1.27 | 4.43 |
| 60 | Xác nhận | 171 | 46.2% | 11.0% | 12.5% | 0.88 | 3.44 |

Cửa sổ đang dùng ở live: 60 phiên. Qua ngưỡng recall 60% ở cả Chọn và Xác nhận: 14. Đạt precision gấp 2 lần nền ở cả hai: không cửa sổ nào.
Ngưỡng được chốt trước lần đo đầu. Số sát ngưỡng không phải lý do để nới ngưỡng, và chọn lại cửa sổ sau khi đã xem các bảng này là một luật mới: phải đo lại từ đầu, và các giai đoạn đã xem không còn là phép thử sạch.

## Danh mục chia đều mã ở ngành mở

Mỗi phiên giữ đều mọi mã của rổ năm đang ở ngành mở, trạng thái tính đến hết phiên trước. Phí 0.3% cả vòng tính trên phần tỷ trọng đổi chủ. Phiên không ngành nào mở thì đứng tiền, lãi 5.5%/năm. "Cả rổ" là cùng cách đó nhưng luôn mở. Cột chính mua ngay giá đóng cửa của phiên vừa cho tín hiệu, là cách lạc quan nhất; cột "trễ 1 phiên" mua ở giá đóng cửa phiên sau, là cách thận trọng. Giá mở cửa nằm giữa hai cột.

| Danh mục | Giai đoạn | Từ | Đến | Lợi nhuận | Mỗi năm | Sụt sâu nhất | Lợi nhuận trễ 1 phiên |
|---|---|---|---|---|---|---|---|
| VN-Index | Lùi | 2015-01-05 | 2020-12-31 | +102.3% | +12.5% | -45.3% | — |
| Cả rổ | Lùi | 2015-01-05 | 2020-12-31 | +206.4% | +20.6% | -41.0% | — |
| Ngành mở 14 phiên | Lùi | 2015-01-05 | 2020-12-31 | -4.6% | -0.8% | -61.9% | -22.6% |
| Ngành mở 30 phiên | Lùi | 2015-01-05 | 2020-12-31 | +44.4% | +6.3% | -53.5% | +50.4% |
| Ngành mở 60 phiên | Lùi | 2015-01-05 | 2020-12-31 | +142.6% | +16.0% | -51.2% | +129.5% |
| VN-Index | Chọn | 2021-01-04 | 2024-12-31 | +14.8% | +3.5% | -40.3% | — |
| Cả rổ | Chọn | 2021-01-04 | 2024-12-31 | +85.9% | +16.8% | -51.0% | — |
| Ngành mở 14 phiên | Chọn | 2021-01-04 | 2024-12-31 | +177.0% | +29.1% | -26.2% | +116.6% |
| Ngành mở 30 phiên | Chọn | 2021-01-04 | 2024-12-31 | +182.5% | +29.7% | -22.0% | +117.9% |
| Ngành mở 60 phiên | Chọn | 2021-01-04 | 2024-12-31 | +53.7% | +11.4% | -60.2% | +62.6% |
| VN-Index | Xác nhận | 2025-01-02 | 2026-10-09 | +37.0% | +19.5% | -18.1% | — |
| Cả rổ | Xác nhận | 2025-01-02 | 2026-10-09 | +6.7% | +3.8% | -21.8% | — |
| Ngành mở 14 phiên | Xác nhận | 2025-01-02 | 2026-10-09 | -25.2% | -15.2% | -44.2% | -28.2% |
| Ngành mở 30 phiên | Xác nhận | 2025-01-02 | 2026-10-09 | -4.7% | -2.7% | -28.9% | +11.5% |
| Ngành mở 60 phiên | Xác nhận | 2025-01-02 | 2026-10-09 | -1.5% | -0.8% | -31.9% | -5.3% |

## Sổ lệnh hiện tại

Cùng luật `Được vào`, dừng lỗ, chốt một phần ba ở +1R, tiền chết 30 phiên và phí như trang /backtest. Cột cửa sổ chỉ thêm một điều: mã phải thuộc rổ năm và ngành đang mở. Mỗi lệnh chỉ rủi ro 1% vốn nên sổ đứng tiền phần lớn thời gian; phần lãi từ giao dịch là chênh lệch so với dòng "Chỉ gửi tiền". Giai đoạn lùi của sổ bắt đầu 2018-02-15, khi chỉ số tài chính quý 4/2017 đã công bố đủ 45 ngày; trước đó cổng cơ bản không chấm được mã nào.

| Sổ | Giai đoạn | Lợi nhuận | Mỗi năm | Sụt sâu nhất | VN-Index cùng kỳ | Lệnh vào | Thắng | Lãi TB mỗi lệnh |
|---|---|---|---|---|---|---|---|---|
| Chỉ gửi tiền | Lùi | +16.5% | +5.5% | +0.0% | | | | |
| Không cổng | Lùi | +20.0% | +6.6% | -1.0% | +4.2% | 17 | 29.4% | +2.4% |
| Ngành mở 14 phiên | Lùi | +17.5% | +5.8% | -0.7% | +4.2% | 9 | 33.3% | +2.1% |
| Ngành mở 30 phiên | Lùi | +17.5% | +5.8% | -0.8% | +4.2% | 10 | 30.0% | +1.9% |
| Ngành mở 60 phiên | Lùi | +21.1% | +6.9% | -0.9% | +4.2% | 11 | 45.5% | +4.7% |
| Chỉ gửi tiền | Chọn | +23.8% | +5.5% | +0.0% | | | | |
| Không cổng | Chọn | +16.7% | +4.0% | -2.1% | +14.8% | 39 | 23.1% | -1.6% |
| Ngành mở 14 phiên | Chọn | +17.9% | +4.2% | -2.1% | +14.8% | 27 | 22.2% | -2.0% |
| Ngành mở 30 phiên | Chọn | +18.6% | +4.4% | -2.1% | +14.8% | 24 | 29.2% | -2.2% |
| Ngành mở 60 phiên | Chọn | +20.1% | +4.7% | -2.1% | +14.8% | 30 | 30.0% | -0.9% |
| Chỉ gửi tiền | Xác nhận | +9.9% | +5.5% | +0.0% | | | | |
| Không cổng | Xác nhận | +8.7% | +4.8% | -1.9% | +37.0% | 21 | 33.3% | +0.4% |
| Ngành mở 14 phiên | Xác nhận | +10.9% | +6.0% | -0.8% | +37.0% | 8 | 37.5% | +2.9% |
| Ngành mở 30 phiên | Xác nhận | +11.2% | +6.2% | -1.9% | +37.0% | 10 | 40.0% | +2.8% |
| Ngành mở 60 phiên | Xác nhận | +9.1% | +5.1% | -0.8% | +37.0% | 10 | 30.0% | -0.3% |

Lưu ý: rổ ứng viên là 106 mã còn sống đến nay, nên mọi con số còn thiên lệch sống sót, nặng nhất ở giai đoạn lùi vì các mã đã hủy niêm yết hay sáp nhập không có mặt. Giai đoạn lùi chỉ để đối chiếu và không nằm trong luật qua cửa. Trong giai đoạn đó tín dụng ngân hàng chỉ có từ 2018, nên trước đó ngân hàng và chứng khoán luôn đóng; dòng tiền khối ngoại chỉ có từ 2018-08, phiên thiếu thì cổng dòng ngoại không chặn.
