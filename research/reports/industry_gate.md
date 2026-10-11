# Cổng ngành

Nến từ 2014-01-02 đến 2026-10-09, 760/800 mã trong danh sách niêm yết đã có nến, trong đó 95 mã đã hủy niêm yết.
Chưa có nến: 40 mã, trong đó 40 mã đã hủy niêm yết trước 2014-01-02 nên nguồn không còn giá.
Rổ của mỗi năm đọc danh sách niêm yết của nguồn nên giữ cả mã đã hủy niêm yết: mã rời sàn vì phá sản hay bị thâu tóm vẫn nằm trong rổ của năm nó còn giao dịch, và chỉ bị loại khi số cổ phiếu đã công bố hoặc thanh khoản không đủ.
Dầu từ 2014-01-02 đến 2026-10-09.
Dòng ngoại từ 2018-08-30 đến 2026-10-09, 734 mã. Nguồn không có trước ngày sớm nhất này.

Rổ 200 mã và rổ giao dịch 100 mã theo vốn hóa: 2014=62/62 từ 2014-01-08, 2015=76/76 từ 2015-01-05, 2016=75/75 từ 2016-01-04, 2017=74/74 từ 2017-01-03, 2018=118/100 từ 2018-01-02, 2019=100/100 từ 2019-01-02, 2020=102/100 từ 2020-01-02, 2021=200/100 từ 2021-01-04, 2022=200/100 từ 2022-01-04, 2023=174/100 từ 2023-01-03, 2024=191/100 từ 2024-01-02, 2025=200/100 từ 2025-01-02, 2026=187/100 từ 2026-01-05.
Chỉ số ngành và cổng ba mã dựng trên rổ 200 mã của năm, nên ngành nào đủ ba mã trong rổ 200 thì mã vào lệnh bị xét theo chỉ số ngành đó kể cả khi rổ giao dịch chỉ có một mã của ngành ấy; cờ mở chỉ sinh cho mã thuộc rổ giao dịch 100 mã.
Mã bị loại khi số cổ phiếu đã công bố chưa đủ 45 ngày tính tới phiên chốt, hoặc khi trung vị giá trị khớp thật 20 phiên trước đó dưới 3 tỷ đồng; mã đã hủy niêm yết không được xếp hạng sau ngày hủy. Vốn hóa và thanh khoản đều đo bằng giá thật và giá trị khớp thật của phiên, không bằng giá đã điều chỉnh chia tách, nên mã chia tách nhiều không còn bị đo thấp mà rơi khỏi rổ.
Ba giới hạn đã biết của cách đo này, chưa đưa vào luật. Một: một phiên mã không khớp lệnh vẫn vào cửa sổ 20 phiên với giá trị 0 nên trung vị bị kéo xuống — trên cả kho, nến volume bằng 0 chiếm 17–25% mỗi năm trong 2014–2020, 7% năm 2021, rồi khoảng 1% từ 2022; nhưng đo đúng 20 phiên cuối của rổ thì không năm nào có phiên giá trị 0, vì mã không khớp lệnh nằm ngoài rổ. Hai: cửa sổ là 20 phiên cuối của chính mã chứ không theo lịch sàn, nên mã bị tạm ngừng giao dịch dài vẫn xếp hạng bằng thanh khoản cũ (HPX trong rổ 2024 xếp hạng 144/200 dù phiên cuối 2023-09-15 cách phiên chốt 109 ngày); bắt nến cuối phải mới hơn một số ngày so với phiên chốt là một tham số mới, chưa đưa vào. Ba: số cổ phiếu phải đủ 45 ngày mới tính trong khi giá thật đã giảm từ ngày giao dịch không hưởng quyền, nên vốn hóa của mã vừa chia tách hay phát hành thêm bị đo lệch trong cửa sổ đó.
Số cổ phiếu lưu hành trước 2023 được bổ sung từ vốn góp của chủ sở hữu trong BCTC quý. Cửa sổ đo chạy từ 2021-01-04, phiên đầu tiên vốn hóa đã biết.

Chọn 2021-01-04–2024: 546 đợt, recall 57.5%, precision ngành 15.0%, tỷ lệ nền 13.0%, ngành mở trung bình mỗi phiên 4.60.
Xác nhận 2025–2026: 175 đợt, recall 41.7%, precision ngành 6.0%, tỷ lệ nền 9.8%, ngành mở trung bình mỗi phiên 2.89.
Lùi 2015–2020, chỉ để đối chiếu: 611 đợt, recall 38.3%, precision ngành 18.1%, tỷ lệ nền 10.7%, ngành mở trung bình mỗi phiên 1.88.
Giai đoạn lùi không nằm trong luật qua cửa. Tín dụng ngân hàng chỉ có từ 2018, nên trước đó ngân hàng và chứng khoán luôn đóng.

Cổng ngành chưa qua cả hai giai đoạn. Được vào chưa đổi.
Chỗ trượt: Chọn recall 57.5%, dưới ngưỡng 60% 2.5 điểm; Chọn precision gấp 1.16 lần nền, cần 2 lần; Xác nhận recall 41.7%, dưới ngưỡng 60% 18.3 điểm; Xác nhận precision gấp 0.61 lần nền, cần 2 lần. Ngưỡng được chốt trước lần đo đầu; số sát ngưỡng không phải lý do để nới ngưỡng.

Danh sách khoanh, chọn: recall 14.0% trên 522 đợt, trung vị nhóm được khoanh trừ nhóm bị loại -0.8%.
Danh sách khoanh, xác nhận: recall 9.1% trên 164 đợt, chênh trung vị -1.0%.
Danh sách khoanh chưa qua cửa, nên chưa lọc ứng viên. Hạng vị thế không được dùng để chặn.
SHS trong rổ giao dịch 8 đợt ở giai đoạn chọn và 3 đợt ở giai đoạn xác nhận, trong đó nằm ở danh sách khoanh 2 và 0 đợt.

Nhận định tháng chạy bằng `python -m app.llm_notes` từ thư mục research, mỗi tháng một lần từ 2021-01-04. Câu hỏi thêm về công bố, chỗ lệch hạng, và rà bảng ngành nằm ở docs/industry-first-backlog.md.
Cửa thoát theo ngành, trailing stop sau khi chốt một phần ba, và trần 132 phiên đã có trong sổ. Trần nắm và việc bỏ tiền chết 30 phiên vẫn tắt vì cổng ngành chưa được phép chặn lệnh.
