# Torroba: mặt nốt, tempo, và câu hát

> **Trạng thái**: đã nghe trên VRE 1M, Guitar, Torroba. Chờ code.
> **Thay cho**: hàng `castillo`, `ctx.bpm > 72` → «một nốt giá ngân cả ô» trong [`docs/sonify-guitar-torroba-phrase-plan.md`](./sonify-guitar-torroba-phrase-plan.md) mục 4.0, và cách gộp hai ô 2/4 thành một ô 4/4 trong [`docs/sonify-guitar-torroba-castillos-frames.md`](./sonify-guitar-torroba-castillos-frames.md) mục 3.3 khi phép gộp đó kéo dài hình nốt.
> **Giữ**: staccato đúng chỗ trong một điệu nhảy. Tám kiểu đã viết. Đường giá `_melody_at`. Không thêm id pattern.

Ba việc cùng một đợt nghe. Mặt nốt của chương 4/4 ở nốt đen = 96 đang quá dài, nên tempo nghe chậm. Câu trữ tình bị phẳng và bị cắt. Các texture đã làm hầu như không vào chương.

---

## 1. Việc đang nghe

VRE 1M, bốn chương. Chương I và chương IV là 4/4, nốt đen = 96. Chương I có Castillo. Chương IV có Olite. Sonatina khi đứng trong chương I cũng cùng một mặt.

Tai nghe ba lớp:

1. Nhát đứt. Nốt đen ở bè trầm, nhất là nốt bấm cao hơn dây buông, tắt giữa lúc câu còn hát. Castillo chương I và các ô Olite chương IV nghe rõ chỗ này. Staccato thỉnh thoảng, đúng vị trí, trong một điệu nhảy, thì là nhạc. Staccato thành cách dựng cả câu thì làm đứt bản.
2. Phẳng. Castillo và Sonatina của chương I không có câu dài, không có contrast, không có chấm phá. Một nốt ngân, hoặc hai tiếng rời cách nhau nửa ô, không phải mặt của Torroba.
3. Chậm. Cùng nốt đen = 96, mặt đang hát là nốt trắng và nốt tròn. Bản gốc của ông chạy bằng móc đơn và móc kép.

Điểm 3 là cảm quan tốc độ. Điểm 1 và điểm 2 là cách dựng câu trên mặt nốt đó. Sửa staccato mà vẫn để nốt trắng thì chương vẫn chậm.

---

## 2. Tempo và mặt nốt

Ngoài một số bài chậm, nhạc Torroba tươi và nhanh. *Torija* trong *Castillos de España* (bản nghe gọi Toriha) là ngoại lệ: Andantino, câu hát, thong thả. Vài bài cùng họ với *Torija* được phép ngân. Phần còn lại không lấy mặt của bài chậm.

*Sonatina* I là Allegretto, 3/4. Đó không phải bản chậm. Cửa và các ô ngân lấy từ *Sonatina* Andante không được thành lưới của một chương nốt đen = 96. *Olite* là Vivace, nốt đen = 95, nhịp 2/4. *Alcañiz* là Allegro. *Zafra* là Allegretto vivace, nốt đen = 110. Các điệu đó đứng ở tempo của chính chúng.

Mặt nốt Torroba viết:

| Hình | Vai |
|---|---|
| Móc kép | Nét chạy, láy, chấm phá |
| Móc đơn | Mặt của câu. Phần lớn tiếng nằm ở đây |
| Nốt đen | Ít. Trụ, hoặc một nhát trong điệu |
| Nốt trắng, nốt tròn | Chỗ ngân có chủ đích bên trong câu. Không phải lưới của cả chương |

Đúng nhịp, đúng tempo, đúng nốt. Đường giá vẫn là `_melody_at`. Đổi độ dài tiếng, hoặc đổi tempo nghe, là đổi bản.

Ở nốt đen = 96, một móc đơn dài khoảng 0,31 giây, một nốt đen dài 0,63 giây, một nốt trắng dài 1,25 giây, một nốt tròn dài 2,5 giây. Chương 4/4 hiện hát như sau:

| Chỗ | Hình đang viết | Nghe ở 96 |
|---|---|---|
| Thân `castillo`, BPM trên 72 | Lead ngân cả ô. 4/4 là nốt tròn, `duration_beats = 4`. Bass một nốt đen ở móc 0 | Một tiếng hát 2,5 giây, rồi bass búng một phách |
| Lưới `sonatina` | Lead và bass chỉ ở phách mạnh, mỗi tiếng một móc đơn. 4/4 là móc 0 và móc 4 | Tiếng mới mỗi nửa ô. Nhịp của câu là nốt trắng |
| Thân `olite` Vivace | Hợp âm ở móc 0 và móc 4. Nét yếu là móc đơn | Cùng nhịp nốt trắng. Móc kép của bản Vivace không có mặt |
| Kiểu 7, ô 1, khi được gọi | Nửa sau ô là nốt trắng, `duration_beats = 2` | Nốt này chỉ hợp lệ khi nó là chỗ ngân trong một câu đã chạy bằng móc đơn và móc kép |

`_span_castillo` trả không có kiểu khi `ctx.bpm > 72`. Chương I đứng ngoài cửa đó. Mọi ô là nốt tròn. Kiểu 7 và kiểu 8, nơi *Arada* hát móc đơn, móc kép và nốt đen chấm dôi, không vào chương 96.

---

## 3. Đổi 2/4 sang 4/4

Engine không có nhịp 2/4. *Olite* gốc là 2/4. Hai ô 2/4 được đặt vào một ô 4/4, hợp âm rơi vào móc 0 và móc 4.

Phép gộp đó chỉ đúng khi đồng hồ của nốt đen giữ nguyên và hình nốt giữ nguyên:

- Một phách 2/4 vẫn là một phách 4/4.
- Móc đơn vẫn dài một móc đơn. Móc kép vẫn dài một móc kép. Nốt đen vẫn dài một nốt đen.
- Hai ô 2/4 kế nhau chiếm đúng bốn phách của một ô 4/4, vì hai ô đó vốn đã là bốn phách.

Kéo một móc đơn thành nốt đen, hoặc một nốt đen thành nốt trắng, làm bản chậm đi một lần. Nốt đen = 95 của *Olite* và nốt đen = 96 của chương 4/4 là cùng một đồng hồ. Sai là độ dài hình nốt, không phải con số BPM.

Nét bảy nốt `5-5-4-2-3-2-0` của *Olite* phải giữ giá trị nốt của bản. Nhét nó vào lưới thưa, hoặc làm tròn cho đủ tám móc bằng cách kéo từng tiếng, là đổi nhịp điệu.

---

## 4. Câu hát

Torroba viết câu dài, giai điệu mượt, rồi chấm phá. Contrast nằm trong câu: chỗ chạy, chỗ láy, chỗ ngân, chỗ một nhát của điệu. Câu không phải một nốt giá lặp lại, cũng không phải một chuỗi nhát rời.

Staccato của Danza, Fandanguillo và hợp âm Olite ở phách mạnh của điệu được giữ. Đó là nhát của điệu, đúng chỗ.

Nốt đen cao ở bè trầm thì khác. `_torroba_bass` được phép trả một nốt bấm trong 40–53, không phải dây buông. Nốt đó đang dài một phách rồi tắt, trong khi lead còn ngân. Dây buông còn vang. Nốt bấm cao tắt thành một nhát, và nhát đó cắt câu. Chương I Castillo và chương IV Olite nghe rõ chỗ này. Bè trầm của câu hát ngân theo câu, hoặc đi bằng móc đơn và móc kép. Nó không búng một nốt đen rồi nghỉ hết ô.

Luyến láy trùm ba là chữ ký. *Arada* viết mordent bộ ba trong một móc đơn, ví dụ `G♯–A–G♯`, có slur. Kiểu 7 đã ghi hình đó, rồi engine rút thành hai móc kép vì chưa có bộ ba `duration_beats = 1/6`. Hai móc kép đó cũng chỉ được gọi khi BPM từ 72 trở xuống. Chương 96 không có láy. Mặt hát cần láy trùm ba, kiểu `E–F–E`, slur, nằm trong câu. Slur của câu dài cũng là mặt đó. `pen.grace` hai móc kép không thay được bộ ba.

Câu êm được xuống thêm. Bậc vi mô hiện là `_MICRO = 2`, sàn 40. Lead Sonatina viết 64, bass còn vang ở 60, nên lead chỉ xuống một bậc, còn 62. Câu êm cần một bậc −4 trên vận tốc đã viết, tức hai lần `_MICRO`, ở những tiếng bản gốc để `p` hoặc nhẹ hơn. Sàn 40 giữ. Bậc −4 không đụng nhát `mf` của điệu.

---

## 5. Texture đã làm, ít được hát

Tám kiểu là mặt móc đơn và móc kép đã chốt trong mục 4 của [`docs/sonify-guitar-torroba-phrase-plan.md`](./sonify-guitar-torroba-phrase-plan.md). Chúng đang bị cửa lịch để ngoài chương 4/4 nhanh.

| Câu | Được gọi | Ô có texture |
|---|---|---|
| `castillo`, BPM trên 72 | không | 0. Cả câu là nốt tròn |
| `castillo`, BPM từ 72 trở xuống, `n` lẻ | không | 0. Câu ngân |
| `sonatina`, `n` lẻ | không | 0. Lưới hai móc đơn |
| `sonatina`, `k % 3 == 0`, dài từ 4 ô | kiểu 4 | 2 ô đầu |
| `sonatina`, `k % 3 == 1`, `rise` từ 3 | kiểu 2 | 2 ô |
| `sonatina`, `k % 3 == 2`, dài từ 3 ô | kiểu 1 | 1 ô |
| `sonatina` đóng | kiểu 3 | 1–3 ô cuối |
| Câu liền trước vừa dùng cùng số kiểu | không | 0 |

Một câu Sonatina 6 ô thắng kiểu 4 thì bốn ô còn lại vẫn là hai móc đơn cách nhau một nốt trắng. Câu lẻ không có kiểu. Castillo của chương I không có kiểu nào. Rasgueado nhẹ, rải chữ V, đối đáp Allegretto, mordent của *Arada* nằm trong code và không vào tai.

Kiểu là cách hát của chương nhanh, không phải đồ trang trí của chương chậm. Cửa `bpm > 72` đang đảo chiều: chương 96, nơi mặt phải dày móc đơn và móc kép, lại nhận nốt tròn. Chương từ 72 trở xuống mới được gọi kiểu 7 và kiểu 8.

---

## 6. Luật khi sửa

1. Nốt đen = 96 trên 4/4 nghe nhanh. Mặt của Castillo, Sonatina và Olite ở tempo đó là móc đơn và móc kép, với một ít nốt đen. Nốt trắng và nốt tròn chỉ đứng ở chỗ ngân đã có trong câu.
2. *Sonatina* I giữ Allegretto. Ô ngân của Andante không phủ thân chương 96.
3. *Torija* và các bài chậm cùng họ được ngân. Chúng không thành lưới mặc định của mọi chương `castillo`.
4. Gộp 2/4 vào 4/4 không nhân độ dài hình nốt. Móc kép, móc đơn và nốt đen giữ giá trị. Đồng hồ nốt đen giữ nguyên.
5. Cao độ của bè cao vẫn là `_melody_at`. Đúng nốt đi cùng đúng nhịp.
6. Staccato của điệu, đúng phách, giữ. Nốt đen bè trầm đang cắt câu hát thì ngân, hoặc đi tiếp bằng móc đơn và móc kép.
7. Luyến láy trùm ba có slur đứng trong câu hát. Hai móc kép không tính là bộ ba đó.
8. Câu êm hạ được −4 trên vận tốc đã viết. Sàn 40 giữ.
9. Kiểu 1 đến kiểu 8 phải chiếm phần hát của chương, kể cả chương 4/4 trên 72 BPM. Một hoặc hai ô ở đầu câu chẵn không đủ. Không thêm id pattern.

---

## 7. Chỗ sửa khi thực hiện

- `backend/app/sonify/guitar_torroba.py`: `_span_castillo` bỏ cửa cấm kiểu khi BPM trên 72. Lưới nền của `castillo` và `sonatina` trên 4/4 nhanh đổi từ nốt tròn và từ hai móc đơn mỗi nửa ô sang mặt móc đơn / móc kép. `_render_castillo_bar` không còn một nốt giá suốt ô ở 96. Bass bấm cao không còn một nốt đen rồi nghỉ.
- `backend/app/sonify/guitar_torroba.py`: lịch kiểu. Câu `n` lẻ và phần ô còn lại của câu chẵn phải nhận texture, không chỉ một hoặc hai ô.
- `backend/app/sonify/guitar_torroba.py` và `backend/app/sonify/guitar_torroba_doors.py`: láy trùm ba. Mordent bộ ba của kiểu 7 viết đủ ba tiếng trong một móc, có slur.
- `backend/app/sonify/guitar_torroba.py`: bậc −4 cho câu êm. `_MICRO` vẫn là 2. Chỗ êm được hai bậc.
- `docs/sonify-guitar-torroba-phrase-plan.md` mục 4.0 và `docs/sonify-guitar-torroba-castillos-frames.md` mục 3.3: thay hàng nốt ngân ở BPM trên 72, và ghi rõ phép gộp 2/4 không kéo dài hình nốt.
- Test khóa hình nốt của chương 4/4 ở 96: thân Castillo và Sonatina không còn nốt tròn làm lưới. Olite giữ giá trị nốt của 2/4. Điệu vẫn còn staccato đúng phách.
