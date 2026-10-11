# Cổng ngành theo cửa sổ 14, 30, 60 phiên

Cửa sổ là số phiên dùng để so lợi suất ngành với VN-Index, và cũng là cửa sổ của chuỗi dầu. Định nghĩa đợt tăng (66 phiên, +20%, cửa sớm dưới +15%), rổ theo năm, ngưỡng tín dụng và VN-Index trên MA200 giữ nguyên. Không có bước nào gọi mô hình ngôn ngữ.

## Tín hiệu

| Cửa sổ | Giai đoạn | Đợt | Recall | Precision ngành | Tỷ lệ nền | Precision / nền | Ngành mở TB |
|---|---|---|---|---|---|---|---|
| 14 | Chọn | 560 | 48.9% | 12.6% | 14.3% | 0.88 | 3.25 |
| 14 | Xác nhận | 171 | 68.4% | 10.7% | 12.5% | 0.85 | 4.05 |
| 30 | Chọn | 560 | 45.9% | 13.0% | 14.3% | 0.91 | 3.26 |
| 30 | Xác nhận | 171 | 60.2% | 10.4% | 12.5% | 0.83 | 3.91 |
| 60 | Chọn | 560 | 45.2% | 11.8% | 14.3% | 0.83 | 3.51 |
| 60 | Xác nhận | 171 | 46.2% | 11.0% | 12.5% | 0.88 | 3.44 |

## Danh mục chia đều mã ở ngành mở

Mỗi phiên giữ đều mọi mã của rổ năm đang ở ngành mở, trạng thái tính đến hết phiên trước. Phí 0.3% cả vòng tính trên phần tỷ trọng đổi chủ. Phiên không ngành nào mở thì đứng tiền, lãi 5.5%/năm. "Cả rổ" là cùng cách đó nhưng luôn mở. Cột chính mua ngay giá đóng cửa của phiên vừa cho tín hiệu, là cách lạc quan nhất; cột "trễ 1 phiên" mua ở giá đóng cửa phiên sau, là cách thận trọng. Giá mở cửa nằm giữa hai cột.

| Danh mục | Giai đoạn | Từ | Đến | Lợi nhuận | Mỗi năm | Sụt sâu nhất | Lợi nhuận trễ 1 phiên |
|---|---|---|---|---|---|---|---|
| VN-Index | Chọn | 2021-01-04 | 2024-12-31 | +13.1% | +3.1% | -40.3% | — |
| Cả rổ | Chọn | 2021-01-05 | 2024-12-31 | +79.5% | +15.8% | -51.0% | — |
| Ngành mở 14 phiên | Chọn | 2021-01-05 | 2024-12-31 | +192.2% | +30.9% | -26.2% | +132.5% |
| Ngành mở 30 phiên | Chọn | 2021-01-05 | 2024-12-31 | +205.0% | +32.3% | -22.0% | +130.3% |
| Ngành mở 60 phiên | Chọn | 2021-01-05 | 2024-12-31 | +41.1% | +9.0% | -60.2% | +59.1% |
| VN-Index | Xác nhận | 2025-01-02 | 2026-10-09 | +37.0% | +19.5% | -18.1% | — |
| Cả rổ | Xác nhận | 2025-01-02 | 2026-10-09 | +6.7% | +3.8% | -21.8% | — |
| Ngành mở 14 phiên | Xác nhận | 2025-01-02 | 2026-10-09 | -25.2% | -15.2% | -44.2% | -28.2% |
| Ngành mở 30 phiên | Xác nhận | 2025-01-02 | 2026-10-09 | -4.7% | -2.7% | -28.9% | +11.5% |
| Ngành mở 60 phiên | Xác nhận | 2025-01-02 | 2026-10-09 | -1.5% | -0.8% | -31.9% | -5.3% |

## Sổ lệnh hiện tại

Cùng luật `Được vào`, dừng lỗ, chốt một phần ba ở +1R, tiền chết 30 phiên và phí như trang /backtest. Cột cửa sổ chỉ thêm một điều: mã phải thuộc rổ năm và ngành đang mở. Mỗi lệnh chỉ rủi ro 1% vốn nên sổ đứng tiền phần lớn thời gian; phần lãi từ giao dịch là chênh lệch so với dòng "Chỉ gửi tiền". Sổ chỉ bắt đầu khi VN-Index đủ 200 phiên, nên giai đoạn chọn bắt đầu từ 2021-11-15.

| Sổ | Giai đoạn | Lợi nhuận | Mỗi năm | Sụt sâu nhất | VN-Index cùng kỳ | Lệnh vào | Thắng | Lãi TB mỗi lệnh |
|---|---|---|---|---|---|---|---|---|
| Chỉ gửi tiền | Chọn | +18.2% | +5.5% | +0.0% | | | | |
| Không cổng | Chọn | +12.8% | +3.9% | -1.8% | -14.2% | 32 | 12.5% | -1.1% |
| Ngành mở 14 phiên | Chọn | +12.4% | +3.8% | -1.8% | -14.2% | 19 | 5.3% | -2.8% |
| Ngành mở 30 phiên | Chọn | +14.7% | +4.5% | -1.5% | -14.2% | 16 | 18.8% | -1.8% |
| Ngành mở 60 phiên | Chọn | +13.9% | +4.2% | -1.5% | -14.2% | 20 | 15.0% | -1.7% |
| Chỉ gửi tiền | Xác nhận | +9.9% | +5.5% | +0.0% | | | | |
| Không cổng | Xác nhận | +13.5% | +7.5% | -1.9% | +37.0% | 27 | 29.6% | +3.1% |
| Ngành mở 14 phiên | Xác nhận | +17.3% | +9.4% | -1.6% | +37.0% | 11 | 36.4% | +10.0% |
| Ngành mở 30 phiên | Xác nhận | +17.7% | +9.6% | -1.9% | +37.0% | 13 | 38.5% | +8.9% |
| Ngành mở 60 phiên | Xác nhận | +8.2% | +4.6% | -0.8% | +37.0% | 12 | 25.0% | -0.9% |

Lưu ý: rổ ứng viên là 106 mã còn sống đến nay, nên mọi con số còn thiên lệch sống sót. Cửa sổ 60 phiên chưa mở được ngành nào trước 2021-04-22, cửa sổ ngắn mở sớm hơn, nên recall năm 2021 nghiêng về cửa sổ ngắn.
