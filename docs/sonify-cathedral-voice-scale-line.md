# Ba bè Preludio, và nốt giữa các mốc scale

> Tham chiếu: [`docs/sonify-la-catedral-preludio.md`](./sonify-la-catedral-preludio.md), [`docs/sonify-guitar-scales-plan.md`](./sonify-guitar-scales-plan.md) Mục 2.1.A
> Phạm vi: ba bè giai điệu của khung Preludio (`_catedral_cell`), và cách `_monotone` chọn nốt giữa hai mốc. Tập nốt của năm nhà giữ nguyên. Cửa sóng, ngân sách 30%, hairpin, và lưới pattern không đổi.

Mỗi khung *La Catedral* dài hai phách, tám móc kép, đếm `1..8`. Ô `4/4` có hai khung. Đếm lại từ `1` ở mỗi khung.

Khung có ba bè giai điệu, cộng bè trầm. Bè cao là đường giá, và mỗi nốt của nó vẫn là nốt giai âm theo `quantize_strong_beats`: phách mạnh về âm hợp âm còn nằm trong giai âm, phách yếu giữ bậc giai âm làm nốt đi qua hoặc nốt lân. Hai bè trung là bè trang trí: chúng chỉ lấy nốt của hợp âm đang ngân trong khung. Không mượn âm giai, không có tie. Mỗi cú gảy là một nốt mới, kể cả khi cao độ trùng nốt trước.

`_resolve` cắt nốt nào dài hơn khoảng cách tới onset kế tiếp trong cùng voice. Hai bè trung ngân chồng nhau, nên chúng là hai voice trong `support`: `event.voice == 2` là trung thấp, `event.voice == 4` là trung cao. Không đưa trung cao vào `comp`, vì `ensemble.py` map `comp` như viola. `_resolve` và `_fill_sixteenths` chạy từng voice, không đóng dấu mọi nốt support thành `2`. `_guitar_part` tách `support` theo `event.voice`, mỗi voice một `<backup>`. `guitar.py` không ép nốt `4` về `2`.

MusicXML mỗi voice có một `<backup>` đầu ô. Mỗi voice đi hết ô bằng nốt và dấu lặng của chính khung đó. Không viết `<tie>`. Không thêm nốt ở đầu ô sau để nối nốt `5` hoặc nốt `8`. `_spell16` tự gắn tie khi một lần gọi cắt qua vạch ô, nên đừng gọi nó cho một nốt vượt ô.

`assert_playable` hiện từ chối bốn nốt đồng thời khi profile không phải `barrios_tremolo`, và từ chối bè trung có cao độ vang trên `65`. Trong khung này có lúc đủ bốn nốt: bass, trung thấp, trung cao, bè cao. Profile `barrios_preludio` cần một cửa hẹp: đúng bốn nốt đó, xếp `bass < trung thấp < trung cao < bè cao`, các cao độ khác nhau, và `_playable` vẫn phải đúng. Cửa đó cũng bỏ trần `65` khi nốt trung vẫn thấp hơn bè cao. Sàn `50` giữ. Cặp âm hợp âm dưới bè cao của Preludio không nằm nổi dưới `65`.

## 1. Ba bè của khung

| Vị trí | Bè | Độ dài | Cao độ |
|---|---|---|---|
| `1` | Cao. Đường giá, trên giai âm | Sáu móc kép, tới nốt `7` | `ctx.melody` tại đầu khung. Trong ô `4/4` đây là phách mạnh, đã về âm hợp âm của giai âm |
| `2` | Trung thấp | Hai móc kép | Một âm hợp âm, gọi là âm thấp |
| `3` | Trung cao | Hai móc kép, phủ `3` và `4` | Một âm hợp âm khác, gọi là âm cao |
| `4` | Trung thấp | Hai móc kép, phủ `4` và `5` | Âm thấp nâng một bậc hoặc hai bậc |
| `5` | Trung cao | Một móc đơn, phủ `5` và `6`, rồi tắt | Đúng cao độ nốt `3` |
| `6` | Trung thấp | Hai móc kép | Đúng cao độ nốt `2` |
| `7` | Cao. Đường giá, trên giai âm | Hai móc kép, hết đúng cuối khung | `ctx.melody` tại nốt `7`. Trong ô `4/4` đây là phách yếu, giữ bậc giai âm |
| `8` | Trung thấp | Một móc kép, chỉ vị trí `8`, rồi tắt | Đúng cao độ nốt `2` |

`_CATEDRAL_LEAD_44` đã là đen chấm dôi rồi móc đơn, hai lần trong ô `4/4`. Lịch bè cao giữ nguyên. Code hiện gảy sáu móc kép ở `2, 3, 4, 5, 6, 8`, mỗi nốt dài `0.25`, và dựng lại chữ V mỗi khung. `_CATEDRAL_SUPPORT_44` khóa lịch đó và sẽ đổi.

Âm lượng và khoảng cách bè ở dưới là mức nền, không phải số cứng. Pipeline đang có — cửa register, `_playable`, hợp âm còn âm nào, và đường velocity của câu — được phép dịch mức đó một bước nhỏ để khung chơi được. Trong một bè, các cú gảy lệch nhau vài bậc velocity, để nốt lặp không phẳng. Bè cao vẫn là bè lớn nhất.

Mức nền velocity, trong `40..70`: bè cao `60`, trung thấp `50`, bass `45`, trung cao `40`.

### 1.1. Chọn hai âm hợp âm

Bè cao của cả vùng preludio được chốt trước, vì trần của bè trang trí phụ thuộc nốt giá. Cao độ đó là `ctx.melody` sau `quantize_strong_beats`, không phải cao độ thô của giá và cũng không phải cặp âm trang trí của khung. Tại khung `k`:

1. Trần của âm cao là nốt `1` của khung này. Nốt `3` và nốt `5` chỉ kêu dưới nốt `1`. Trần của âm thấp là nốt thấp hơn trong cặp nốt `1` và nốt `7`, vì nốt `6` và nốt `8` còn kêu dưới nốt `7`. Nốt `5` và nốt `8` không kêu sang khung sau, nên không lấy nốt `1` của khung sau làm trần.
2. Lấy các âm của hợp âm đang ngân, nằm nghiêm giữa bass và trần, và không dưới sàn `50`.
3. Chọn hai âm khác nhau. Âm cao dành cho nốt `3` và `5`. Âm thấp dành cho nốt `2`, `6`, `8`. Trong khung, `3 = 5` và `2 = 6 = 8`.
4. Mức nền của khoảng cách: âm cao cách âm thấp một quãng ba (`3` hoặc `4` bán cung). Nốt bè cao thấp nhất đang kêu cùng âm cao cách âm cao đó nửa octave (`6` bán cung) hoặc một quãng năm (`7` bán cung). Hết đúng khoảng đó thì nới hoặc rút một bước, vừa đủ để còn âm hợp âm, còn `_playable`, và còn `bass < âm thấp < nốt 4 < âm cao < bè cao`. Nốt `4` nâng hai bậc khi nốt đó còn là âm hợp âm và còn thấp hơn âm cao; không thì nâng một bậc. Một bậc cũng chạm âm cao hoặc bè cao thì nốt `4` giữ đúng âm thấp.
5. Hết hai âm trong cửa sổ thì giữ cặp của khung trước, nếu cả hai còn nằm giữa bass và trần. Không thêm âm ngoài hợp âm. Ngoại lệ duy nhất là nốt `4` khi nó nâng một bậc.

Nốt `4` nâng theo thang của mode. Hai bậc chỉ khi nốt đích còn là âm hợp âm và còn thấp hơn âm cao. Một bậc là bước thang liền trên âm thấp, kể cả khi bước đó rời hợp âm.

Mỗi khung, kể cả khung sau vạch ô, đều mở như khung đầu vùng. Bè trung thấp nghỉ một móc kép ở vị trí `1`, rồi gảy nốt `2`. Bè trung cao nghỉ hai móc kép đầu, rồi gảy nốt `3`. Đầu ô mới không có nốt ghép của nốt `5` hay nốt `8` khung trước.

### 1.2. Viết độ dài, không tie

Trong một voice, nốt và dấu lặng đặt sát nhau cho đủ ô. Không có `<tie>`.

Trong một khung, gốc thời gian là đầu khung:

- Nốt `5` bắt đầu ở vị trí `5`, dài một móc đơn (`0.5` phách), tắt ở đầu vị trí `7`. Hai móc kép còn lại của bè trung cao là dấu lặng.
- Nốt `8` bắt đầu ở vị trí `8`, dài một móc kép (`0.25` phách), tắt đúng cuối khung. Vị trí `1` của khung sau là dấu lặng của bè trung thấp, không phải phần nối của nốt `8`.

Khung cuối vùng và khung trước một pattern khác cũng vậy. Không có nốt tràn sang ô kế.

`_render_catedral_preludio_bar` hiện làm từng ô một. Trần của âm thấp cần nốt `7` cùng khung, nên đường bè cao của khung đó có trước khi chọn âm trang trí.

### 1.3. Ô `3/4` và `6/8`

Hai phách đầu vẫn là khung tám móc kép của Mục 1. Phách thừa vẫn là nhóm đi xuống của `_catedral_tail`, bắt đầu tại `beat 2.0`. Nốt `5` đã tắt tại `beat 1.5`. Nốt `8` tắt đúng `beat 2.0`. Không bè nào của khung đè lên nhóm đi xuống, và không viết nốt nối sang nhóm đó.

## 2. Scale: tập nốt giữ, cách đi giữa hai mốc đổi

Các tập sau là đúng và không sửa:

| Nhà | Tập một bước |
|---|---|
| Bach, trưởng | `{0,2,4,5,7,9,11}` |
| Bach, thứ, sóng lên | Thứ giai điệu `{0,2,3,5,7,9,11}` |
| Bach, thứ, sóng xuống | Thứ tự nhiên `{0,2,3,5,7,8,10}`. Nâng bậc 6 và 7 khi mốc đích là chủ âm |
| Sor | `_walk` trên trưởng hoặc thứ tự nhiên |
| Barrios | Cùng bước với Sor. Nửa cung chỉ ở nốt ngay trước mốc |
| Villa | Tập của mode cộng `{2,5,10}`. Dây buông là nước sau, chỉ trên móc kép |
| Brouwer | Dorian ∪ Phrygian `{0,1,2,3,5,7,8,9,10}`, ưu tiên cả cung |

Mốc vẫn là `ctx.melody` trên phách mạnh, trên đích, và trên chỗ giá đi ngang vào phách.

`_monotone` hiện tới mốc sớm nhất rồi nhắc lại cao độ. `_step_pitch` còn ép `±1` hoặc `±2` ra ngoài tập. Hai việc đó làm năm nhà giống nhau ở giữa câu.

### 2.1. Bước tối thiểu là bước trong tập

`room_steps = ceil(|end - cursor| / 2)` là biên cứng: với bước không quá hai bán cung, còn đủ nốt để về đích hay không.

`scale_need` là số bước thực sự đi trong tập của nhà từ `cursor` tới `end`. Từ `E4` lên `C5` trong Đô trưởng là tám bán cung, `room_steps = 4`, nhưng thang âm cần năm bước vì `E–F` và `B–C` chỉ rộng một bán cung. Bước thừa trong tập chỉ có khi `left_after > scale_need`.

Một vòng neighbor là hai bước: đi ra một bậc, rồi về. Dư đúng một bước thì không đủ một vòng.

- Bach, Barrios, Brouwer: bước lẻ đó được dùng nếu có một nốt nửa cung hợp lệ nằm giữa hai đầu và cách mỗi đầu không quá hai bán cung.
- Sor: không có nốt đó trong thang thì nhắc lại một cao độ. `C4 → D4` trong hai bước chỉ còn `[60, 60, 62]` hoặc `[60, 62, 62]`.

`_step_pitch` chỉ ép `±1` hoặc `±2` ra ngoài tập khi không còn bước nào trong tập về được mốc. Retreat vẫn đảo chiều đúng `retreat_spans`. Hoa mỹ khi giá đứng yên vẫn là một bậc trong tập, rồi về mốc. Câu đó đã có trong `ornament=True`; `ornament=False` trên giá đứng vẫn được nhắc cao độ.

### 2.2. Bước thừa của từng nhà

**Bach.** Nốt ngay trước mốc là `end - 1`, nếu nốt đứng trước cách nó không quá hai bán cung và bước vào `end` đi lên một bán cung. Đó là cảm âm vào đúng nốt mốc, kể cả khi nốt đó nằm ngoài `bach_scale_classes` (`D♯` trước `E` trong Đô trưởng). Khi câu đi từ phía trên xuống mốc, vòng thừa là bậc diatonic phía trên rồi rơi về `end`, đặt ở cuối câu. Thân câu vẫn ở trong tập.

**Sor.** Vòng thừa là bậc diatonic phía trên mốc khi câu đi lên (`_walk(end, +1)`), hoặc neighbor ngay sau `start` rồi mới đi về `end`. Sor không đặt `end - 1` vào nốt cuối nếu bậc đó chỉ là nửa cung ngoài thang. Vì vậy khi vào `C` hoặc `F`, Bach kết `… C, B, C` còn Sor kết `… C, D, C`, hoặc Sor đưa neighbor lên đầu câu.

**Barrios.** Thân câu diatonic như Sor, nhưng slot `anchor - 1` để trống cho `barrios_chromatic_approach` trong `_color_line`. `_monotone` chốt `anchor - 2` sao cho cách nốt nửa cung đó không quá hai bán cung, và bản thân `anchor - 2` không phải một nửa cung thứ hai. Nếu không chừa slot này, `_color_line` ghi đè neighbor của Sor, hoặc bỏ nửa cung Barrios vì bước vào nó rộng hơn hai bán cung.

**Villa.** Trong `_monotone`, bước thừa và bước thường ưu tiên âm màu `{2, 5, 10}` trước bậc diatonic, khi bước đó còn về kịp mốc. Dây buông không chọn ở đây. `_color_line` mới thử dây buông, và chỉ trên slot `dur16 == 1` khi `bpm >= 88`, đúng như `test_villa_open_strings_wait_for_sixteenth_runs`. Chùm móc kép trượt `_groups_ok` thì trả lại đường nốt bấm. Không hủy `ScalePassage`.

**Brouwer.** Nốt giữa không được chạm `end` rồi đứng lại trước khi câu hết. Khi cả bước một bán cung và bước hai bán cung đều về kịp, lấy bước hai bán cung, và lấy bậc mode nằm ngoài ba âm của hợp âm mốc nếu bậc đó có trong tập. Bậc `0, 3, 5, 7` vẫn được đi lướt qua khi đó là nốt duy nhất nối được quãng trong giới hạn hai bán cung. Cấm chúng thì câu dài hơn quãng ba gãy, vì tập không có `4`, `6`, `11`.

### 2.3. Tầm câu dài

`_lead_ok` hiện buộc mọi nốt scale vang trong `59..81`. Câu dài vì thế không có chỗ chạy.

Mỗi câu, kể cả câu ngắn, được phép lệch khỏi đường thẳng giữa hai mốc đúng một bậc: một hoặc hai bán cung. Đó là neighbor ở Mục 2.2, vẫn từng bước không quá hai bán cung.

Câu dài ít nhất một ô mới được nới tầm, và chỉ khi nốt scale còn cao hơn bass đang ngân:

| Nhà | Sàn, cao độ vang | Trần |
|---|---|---|
| Bach, Sor, Barrios | `52` | `83` |
| Villa, Brouwer | `40`, dây Mi trầm buông | `83` |

Villa và Brouwer chạm `40` khi dây buông đó là một bước của câu và bass không đang chiếm nó. Bach, Sor, Barrios dừng ở `52`: câu hát của họ không biến thành bè trầm. Không có nhà nào xuống Rê trầm. Dây sáu của model là Mi (`_OPENS` bắt đầu ở `40`); hạ dây thành Rê là một cách lên dây khác, chưa có trong score.

Câu ngắn hơn một ô giữ cửa `59..81`, cộng đúng một bậc neighbor.

## 3. Chỗ sửa và chỗ giữ

Sửa `_catedral_cell`, `_catedral_wave`, và `_catedral_schedule` theo Mục 1. Bè trung thấp (`voice 2`) và bè trung cao (`voice 4`) cùng nằm trong `support`. `_resolve`, `_fill_sixteenths`, `_guitar_part`, `guitar.py`, và `assert_playable` tách theo `event.voice`. Bỏ tie và chữ V. Mở cửa bốn nốt và bỏ trần `65` đúng như đoạn đầu, chỉ profile `barrios_preludio`. Nốt `5` dài một móc đơn, nốt `8` dài một móc kép, và đầu ô sau không có nốt ghép của hai nốt đó. Trước `_catedral_tail`, nốt `5` đã tắt tại `beat 1.5` và nốt `8` tắt đúng `beat 2.0`.

Sửa `_monotone` và cửa ép của `_step_pitch`. Nới `_lead_ok` theo Mục 2.3. `bach_scale_step`, `classic_scale_step`, `barrios_scale_step`, `villa_scale_step`, `brouwer_scale_step` giữ tập nốt. Dây buông Villa vẫn nằm trong `_color_line`.

Giữ lịch bè cao của `_CATEDRAL_LEAD_44`, bass pedal, cửa scale, ngân sách, và hairpin. Mức nền velocity là bè cao `60`, trung thấp `50`, bass `45`, trung cao `40`. Pipeline được phép dịch mức nền. Trong một bè, các cú gảy lệch nhau vài bậc velocity.

Hai test đang khóa đường tới-rồi-nhắc-lại, và sẽ đổi kỳ vọng khi có bước quay:

- `test_straight_raw_does_not_invent_a_retreat_and_a_real_one_lands` đòi cả câu đi lên không đổi chiều.
- `test_flat_price_steps_to_a_neighbor_instead_of_repeating` đòi `_monotone(64, 67, 4, …)` đi lên suốt.

Retreat thật vẫn phải đi xuống trong `retreat_spans`. Quay đầu của neighbor là hai bước có chủ đích, không phải retreat giả.

Cửa nghe sau khi sửa:

- Một ô `4/4` có hai khung. Bè cao ở `1` và `7`. Trung thấp ở `2`, `4`, `6`, `8`. Trung cao ở `3` và `5`. Không có `<tie>`.
- Trong một khung, `2 = 6 = 8` và `3 = 5`. Nốt `4` cao hơn `2` một bậc hoặc hai bậc. Trung cao cách trung thấp một quãng ba. Nốt thấp nhất của bè cao cách trung cao nửa octave hoặc một quãng năm.
- Hai bè trung chỉ dùng âm của hợp âm đang ngân, trừ nốt `4` khi nó nâng một bậc.
- Bốn nốt xếp `bass < trung thấp < trung cao < bè cao`. `assert_playable` chấp nhận đúng thế của profile `barrios_preludio`, kể cả khi bè trung vượt `65` mà vẫn thấp hơn bè cao.
- Nốt `5` dài một móc đơn và tắt ở đầu vị trí `7`. Nốt `8` dài một móc kép và tắt ở cuối khung. Đầu ô sau không có nốt ghép của hai nốt đó. Trước `_catedral_tail`, nốt `5` tắt tại `beat 1.5` và nốt `8` tắt đúng `beat 2.0`.
- Quãng ba và quãng năm, cùng bốn mức velocity, là mức nền. Pipeline được phép nới một bước cho khung chơi được. Cùng một bè, các cú gảy không cùng một velocity.
- Bach trưởng vào `C` kết bằng `B–C`. Sor trưởng vào `C` kết bằng `D–C` hoặc neighbor ở đầu câu.
- Câu Villa dưới 88 BPM, và các móc đơn đầu câu dài, không gọi `villa_open_candidates`.
- Câu dài của Villa hoặc Brouwer có thể chạm Mi trầm buông. Câu của Bach, Sor, Barrios không xuống dưới `52`.
