# Cổng ngành

Nến từ 2014-01-02 đến 2026-10-09, 760/800 mã trong danh sách niêm yết đã có nến, trong đó 95 mã đã hủy niêm yết.
Chưa có nến: 40 mã, trong đó 40 mã đã hủy niêm yết trước 2014-01-02 nên nguồn không còn giá.
Rổ của mỗi năm đọc danh sách niêm yết của nguồn nên giữ cả mã đã hủy niêm yết: mã rời sàn vì phá sản hay bị thâu tóm vẫn nằm trong rổ của năm nó còn giao dịch, và chỉ bị loại khi số cổ phiếu đã công bố hoặc thanh khoản không đủ.
Dầu từ 2014-01-02 đến 2026-10-09.
Dòng ngoại từ 2018-08-30 đến 2026-10-09, 734 mã. Nguồn không có trước ngày sớm nhất này.

Rổ 200 mã và rổ giao dịch 100 mã theo vốn hóa: 2014=62/62 từ 2014-01-08, 2015=76/76 từ 2015-01-05, 2016=75/75 từ 2016-01-04, 2017=74/74 từ 2017-01-03, 2018=118/100 từ 2018-01-02, 2019=100/100 từ 2019-01-02, 2020=102/100 từ 2020-01-02, 2021=200/100 từ 2021-01-04, 2022=200/100 từ 2022-01-04, 2023=174/100 từ 2023-01-03, 2024=191/100 từ 2024-01-02, 2025=200/100 từ 2025-01-02, 2026=187/100 từ 2026-01-05.
Mã bị loại khi số cổ phiếu đã công bố chưa đủ 45 ngày tính tới phiên chốt, hoặc khi trung vị giá trị khớp thật 20 phiên trước đó dưới 3 tỷ đồng; mã đã hủy niêm yết không được xếp hạng sau ngày hủy. Vốn hóa và thanh khoản đều đo bằng giá thật và giá trị khớp thật của phiên, không bằng giá đã điều chỉnh chia tách, nên mã chia tách nhiều không còn bị đo thấp mà rơi khỏi rổ.
Số cổ phiếu lưu hành trước 2023 được bổ sung từ vốn góp của chủ sở hữu trong BCTC quý. Cửa sổ đo chạy từ 2021-01-04, phiên đầu tiên vốn hóa đã biết.

Chọn 2021-01-04–2024: 546 đợt, recall 57.1%, precision ngành 16.0%, tỷ lệ nền 13.0%, ngành mở trung bình mỗi phiên 5.01.
Xác nhận 2025–2026: 175 đợt, recall 46.3%, precision ngành 7.9%, tỷ lệ nền 9.8%, ngành mở trung bình mỗi phiên 4.92.
Lùi 2015–2020, chỉ để đối chiếu: 611 đợt, recall 38.3%, precision ngành 17.8%, tỷ lệ nền 10.7%, ngành mở trung bình mỗi phiên 1.87.
Giai đoạn lùi không nằm trong luật qua cửa. Tín dụng ngân hàng chỉ có từ 2018, nên trước đó ngân hàng và chứng khoán luôn đóng.

Cổng ngành chưa qua cả hai giai đoạn. Được vào chưa đổi.
Chỗ trượt: Chọn recall 57.1%, dưới ngưỡng 60% 2.9 điểm; Chọn precision gấp 1.24 lần nền, cần 2 lần; Xác nhận recall 46.3%, dưới ngưỡng 60% 13.7 điểm; Xác nhận precision gấp 0.81 lần nền, cần 2 lần. Ngưỡng được chốt trước lần đo đầu; số sát ngưỡng không phải lý do để nới ngưỡng.

Danh sách khoanh, chọn: recall 13.8% trên 522 đợt, trung vị nhóm được khoanh trừ nhóm bị loại -1.1%.
Danh sách khoanh, xác nhận: recall 12.2% trên 164 đợt, chênh trung vị -0.2%.
Danh sách khoanh chưa qua cửa, nên chưa lọc ứng viên. Hạng vị thế không được dùng để chặn.
SHS trong rổ giao dịch 8 đợt ở giai đoạn chọn và 3 đợt ở giai đoạn xác nhận, trong đó nằm ở danh sách khoanh 2 và 0 đợt.

Nhận định tháng chạy bằng `python -m app.llm_notes` từ thư mục research, mỗi tháng một lần từ 2021-01-04. Câu hỏi thêm về công bố, chỗ lệch hạng, và rà bảng ngành nằm ở docs/industry-first-backlog.md.
Cửa thoát theo ngành, trailing stop sau khi chốt một phần ba, và trần 132 phiên đã có trong sổ. Trần nắm và việc bỏ tiền chết 30 phiên vẫn tắt vì cổng ngành chưa được phép chặn lệnh.
