# Cổng ngành theo cửa sổ 14, 30, 60 phiên

Nến từ 2014-01-02 đến 2026-10-09, 331 mã.
Bảng sàn: 709 mã từ `backend/data/vstock.db`, 325/331 mã của rổ có sàn; BAM, BHS, GTN, KLS, KSA, ROS không có nên dùng biên độ rộng nhất.
Tin từ 2024-01-02, dòng ngoại từ 2018-08-30.

Cửa sổ là số phiên dùng để so lợi suất ngành với VN-Index, và cũng là cửa sổ của chuỗi dầu. Định nghĩa đợt tăng (66 phiên, +20%, cửa sớm dưới +15%), rổ theo năm, ngưỡng tín dụng và VN-Index trên MA200 giữ nguyên. Không có bước nào gọi mô hình ngôn ngữ.

## Tín hiệu

| Cửa sổ | Giai đoạn | Đợt | Recall | Precision ngành | Tỷ lệ nền | Precision / nền | Ngành mở TB |
|---|---|---|---|---|---|---|---|
| 14 | Lùi | 611 | 53.0% | 15.8% | 10.7% | 1.47 | 2.24 |
| 14 | Chọn | 546 | 61.0% | 15.7% | 13.0% | 1.21 | 4.56 |
| 14 | Xác nhận | 175 | 66.9% | 7.4% | 9.8% | 0.75 | 5.57 |
| 30 | Lùi | 611 | 48.1% | 16.2% | 10.7% | 1.51 | 2.05 |
| 30 | Chọn | 546 | 57.7% | 15.6% | 13.0% | 1.20 | 4.64 |
| 30 | Xác nhận | 175 | 59.4% | 6.7% | 9.8% | 0.68 | 5.37 |
| 60 | Lùi | 611 | 38.3% | 17.8% | 10.7% | 1.66 | 1.87 |
| 60 | Chọn | 546 | 57.1% | 16.0% | 13.0% | 1.24 | 5.01 |
| 60 | Xác nhận | 175 | 46.3% | 7.9% | 9.8% | 0.81 | 4.92 |

Cửa sổ đang dùng ở live: 60 phiên. Qua ngưỡng recall 60% ở cả Chọn và Xác nhận: 14. Đạt precision gấp 2 lần nền ở cả hai: không cửa sổ nào.
Ngưỡng được chốt trước lần đo đầu. Số sát ngưỡng không phải lý do để nới ngưỡng, và chọn lại cửa sổ sau khi đã xem các bảng này là một luật mới: phải đo lại từ đầu, và các giai đoạn đã xem không còn là phép thử sạch.

## Danh mục chia đều mã ở ngành mở

Mỗi phiên giữ đều mọi mã của rổ năm đang ở ngành mở, trạng thái tính đến hết phiên trước. Phí 0.3% cả vòng tính trên phần tỷ trọng đổi chủ. Phiên không ngành nào mở thì đứng tiền, lãi 5.5%/năm. "Cả rổ" là cùng cách đó nhưng luôn mở. Cột chính mua ngay giá đóng cửa của phiên vừa cho tín hiệu, là cách lạc quan nhất; cột "trễ 1 phiên" mua ở giá đóng cửa phiên sau, là cách thận trọng. Giá mở cửa nằm giữa hai cột.

| Danh mục | Giai đoạn | Từ | Đến | Lợi nhuận | Mỗi năm | Sụt sâu nhất | Lợi nhuận trễ 1 phiên |
|---|---|---|---|---|---|---|---|
| VN-Index | Lùi | 2015-01-05 | 2020-12-31 | +102.3% | +12.5% | -45.3% | — |
| Cả rổ | Lùi | 2015-01-05 | 2020-12-31 | +17.4% | +2.7% | -47.4% | — |
| Ngành mở 14 phiên | Lùi | 2015-01-05 | 2020-12-31 | -12.9% | -2.3% | -51.6% | -41.5% |
| Ngành mở 30 phiên | Lùi | 2015-01-05 | 2020-12-31 | -13.7% | -2.4% | -56.8% | +7.7% |
| Ngành mở 60 phiên | Lùi | 2015-01-05 | 2020-12-31 | -25.2% | -4.7% | -63.8% | -28.4% |
| VN-Index | Chọn | 2021-01-04 | 2024-12-31 | +14.8% | +3.5% | -40.3% | — |
| Cả rổ | Chọn | 2021-01-04 | 2024-12-31 | +57.8% | +12.1% | -53.4% | — |
| Ngành mở 14 phiên | Chọn | 2021-01-04 | 2024-12-31 | +179.7% | +29.4% | -22.9% | +86.6% |
| Ngành mở 30 phiên | Chọn | 2021-01-04 | 2024-12-31 | +107.1% | +20.0% | -28.5% | +53.8% |
| Ngành mở 60 phiên | Chọn | 2021-01-04 | 2024-12-31 | +40.7% | +8.9% | -53.9% | +34.7% |
| VN-Index | Xác nhận | 2025-01-02 | 2026-10-09 | +37.0% | +19.5% | -18.1% | — |
| Cả rổ | Xác nhận | 2025-01-02 | 2026-10-09 | +9.9% | +5.5% | -21.0% | — |
| Ngành mở 14 phiên | Xác nhận | 2025-01-02 | 2026-10-09 | -6.1% | -3.5% | -30.2% | -10.3% |
| Ngành mở 30 phiên | Xác nhận | 2025-01-02 | 2026-10-09 | +2.5% | +1.4% | -22.8% | +5.5% |
| Ngành mở 60 phiên | Xác nhận | 2025-01-02 | 2026-10-09 | -3.7% | -2.1% | -35.0% | -0.5% |

## Sổ lệnh hiện tại

Cùng luật `Được vào`, dừng lỗ, chốt một phần ba ở +1R, tiền chết 30 phiên và phí như trang /backtest. Cột cửa sổ chỉ thêm một điều: mã phải thuộc rổ năm và ngành đang mở. Mỗi lệnh chỉ rủi ro 1% vốn nên sổ đứng tiền phần lớn thời gian; phần lãi từ giao dịch là chênh lệch so với dòng "Chỉ gửi tiền". Giai đoạn lùi của sổ bắt đầu 2018-02-15, khi chỉ số tài chính quý 4/2017 đã công bố đủ 45 ngày; trước đó cổng cơ bản không chấm được mã nào.

| Sổ | Giai đoạn | Lợi nhuận | Mỗi năm | Sụt sâu nhất | VN-Index cùng kỳ | Lệnh vào | Thắng | Lãi TB mỗi lệnh |
|---|---|---|---|---|---|---|---|---|
| Chỉ gửi tiền | Lùi | +16.5% | +5.5% | +0.0% | | | | |
| Không cổng | Lùi | +21.7% | +7.1% | -1.8% | +4.2% | 30 | 30.0% | +2.3% |
| Ngành mở 14 phiên | Lùi | +19.2% | +6.3% | -0.4% | +4.2% | 9 | 33.3% | +3.1% |
| Ngành mở 30 phiên | Lùi | +18.9% | +6.2% | -0.4% | +4.2% | 11 | 27.3% | +2.8% |
| Ngành mở 60 phiên | Lùi | +17.6% | +5.8% | -0.6% | +4.2% | 9 | 22.2% | +1.5% |
| Chỉ gửi tiền | Chọn | +23.8% | +5.5% | +0.0% | | | | |
| Không cổng | Chọn | +16.5% | +3.9% | -4.1% | +14.8% | 79 | 21.5% | -0.5% |
| Ngành mở 14 phiên | Chọn | +18.2% | +4.3% | -1.6% | +14.8% | 30 | 26.7% | -1.5% |
| Ngành mở 30 phiên | Chọn | +18.7% | +4.4% | -1.6% | +14.8% | 32 | 31.2% | -1.4% |
| Ngành mở 60 phiên | Chọn | +21.9% | +5.1% | -1.6% | +14.8% | 32 | 34.4% | -0.2% |
| Chỉ gửi tiền | Xác nhận | +9.9% | +5.5% | +0.0% | | | | |
| Không cổng | Xác nhận | +4.8% | +2.7% | -4.1% | +37.0% | 37 | 27.0% | -0.6% |
| Ngành mở 14 phiên | Xác nhận | +9.1% | +5.1% | -1.9% | +37.0% | 10 | 30.0% | -0.2% |
| Ngành mở 30 phiên | Xác nhận | +8.9% | +5.0% | -1.9% | +37.0% | 10 | 30.0% | +0.0% |
| Ngành mở 60 phiên | Xác nhận | +9.1% | +5.1% | -0.8% | +37.0% | 10 | 30.0% | -0.2% |

Lưu ý: rổ mỗi năm là 200 mã còn niêm yết theo danh sách của nguồn và đủ thanh khoản, rổ giao dịch là 100 mã đầu theo vốn hóa, nên mã đã hủy niêm yết vẫn có mặt trong năm mà nó còn giao dịch. Giai đoạn lùi vẫn không nằm trong luật qua cửa. Trong giai đoạn đó tín dụng ngân hàng chỉ có từ 2018, nên trước đó ngân hàng và chứng khoán luôn đóng; dòng tiền khối ngoại chỉ có từ 2018-08, phiên thiếu thì cổng dòng ngoại không chặn. Vốn hóa và thanh khoản của rổ đo bằng giá thật và giá trị khớp thật của phiên, không bằng giá đã điều chỉnh chia tách. Số cổ phiếu của nhiều mã đã hủy niêm yết chỉ còn lại ở khoản vốn góp chủ sở hữu trong BCTC quý, nên vốn hóa của chúng là ước lượng, và các ô của giai đoạn lùi chỉ là đối chiếu.
