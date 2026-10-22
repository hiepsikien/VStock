# Bộ nhạc cụ MuseSounds cho bốn kiểu nghe

Đề xuất hai bộ thêm cho mỗi variant. Năm vai trong bản nhạc giữ nguyên. Chỉ đổi nhạc cụ gắn vào từng vai. Mọi giọng dưới đây đều đang cài, `state = 1`, trong thư viện MuseSounds trên máy soạn.

Năm vai, đúng thứ tự part trong `musicxml.py`:

| Part | Vai |
|---|---|
| P5 | Điểm cao, thưa |
| P1 | Giai điệu |
| P2 | Bè giữa |
| P3 | Hợp âm hoặc lớp đệm |
| P4 | Bass |

## Ràng buộc của thư viện

Thư viện không có synth lead, synth pad, hay contrabass pizzicato. Jazz và Tối giản vẫn để bass là `Electric Bass`: bass đi bộ và nhịp bốn phách cần tiếng bật, trong khi `Contrabasses` và `Tuba` ngân bằng hơi hoặc vĩ.

Nốt dài của Ambient, và pad của Tối giản, chỉ giao cho hơi, dây hoặc giọng hát. Chuông, hộp nhạc và pad GM tắt ngay sau tiếng đánh, nên một nốt tròn trên giấy nghe thành nốt rời.

`_MUSE_VOICES` trong `backend/app/sonify/audio.py` hiện trỏ một phần các giọng này. Bộ mới cần thêm tên MusicXML và id nhạc cụ trước khi MuseScore gắn được đúng giọng.

## Giao hưởng

Bộ đang phát: Flute 1, Violins 1, Cellos, Piano, Electric Bass. Giai điệu violin nằm khoảng Sol3–Đô6. Flute điểm ở Sol5–Mi6. Bass vang ở C2–Si2.

Bộ gỗ hợp với những phiên ở `mp`. Bộ đồng hợp với những đoạn thanh khoản lên `mf`–`f`.

### Gỗ

| Vai | Nhạc cụ | Giọng MuseSounds |
|---|---|---|
| P5 | Piccolo | Piccolo |
| P1 | Oboe | Oboe |
| P2 | Clarinet in B♭ | Clarinet in Bb |
| P3 | Harp | Harp |
| P4 | Contrabassoon | Contrabassoon |

Oboe hát trong vùng violin. Nốt dưới Si♭3 gập lên một quãng tám. Clarinet nhận bè cello. Đáy kèn là Rê3, nên nốt dưới Rê3 gập lên một quãng tám: ở giọng Đô đó là Đô3, ở giọng La và Si♭ bè này xuống tới La2. Harp đánh hợp âm hai khuông. Contrabassoon chơi đường bass hiện tại, gồm nốt quãng tám. Dịch giọng đưa gốc xuống tới La1, và kèn vẫn ngân được vùng đó.

### Đồng

| Vai | Nhạc cụ | Giọng MuseSounds |
|---|---|---|
| P5 | Glockenspiel | Glockenspiel |
| P1 | Trumpet | Trumpet |
| P2 | Trombone | Trombone |
| P3 | Sáu kèn cor | French Horns a6 |
| P4 | Tuba | Tuba |

Glockenspiel giữ vai điểm sáng ngắn của flute. Trumpet hát đến khoảng Si♭5; nốt cao hơn thì gập xuống. Trombone là bè giữa. Sáu kèn cor đệm hợp âm trong Fa2–Sol♯4, khác kèn cor đơn đang làm tiếng nở ở Ambient. Fill móc đơn cuối câu của piano lên tới Sol5; trên bộ này fill dừng ở Fa5. Tuba chơi đường bass hiện tại, gồm cả khi dịch giọng.

## Jazz

Bộ đang phát: Vibraphone, Alto Sax, Tenor Sax, Suitcase Piano, Electric Bass. Cụm điểm cao nằm ở C6–F6. Giai điệu alto ở Sol3–La♭5, bè tenor ở C3–C4, hợp âm ở Fa2–Mi5.

### Soul

| Vai | Nhạc cụ | Giọng MuseSounds |
|---|---|---|
| P5 | Guitar điện LP | Electric LP - Clean |
| P1 | Trumpet | Trumpet |
| P2 | Trombone | Trombone |
| P3 | Wurly | Wurly 200A |
| P4 | Electric Bass | Electric Bass |

### Organ và sax

| Vai | Nhạc cụ | Giọng MuseSounds |
|---|---|---|
| P5 | Guitar điện SC | Electric SC - Clean |
| P1 | Soprano Sax | Soprano Saxophone |
| P2 | Baritone Sax | Baritone Saxophone |
| P3 | Hammond | Hammond Organ |
| P4 | Electric Bass | Electric Bass |

Guitar chỉ đánh cụm ngắn ở C6–F6. LP và SC là hai giọng khác nhau trong Muse Guitars Vol. 1. Trumpet chạm trần ở La♭5. Điểm giao soprano và baritone dời từ Sol3 lên La♭3, đúng đáy thực của soprano. Nốt chạm đáy sang baritone, soprano giữ nguyên đường nét. Baritone nhận thêm đoạn đó và vẫn hát thoải mái tới Fa4. Wurly và Hammond đánh được hợp âm Fa2–Mi5.

## Tối giản

Bộ đang phát là synth GM, qua MS Basic: Synth Bell, Synth Arpeggio, Synth Pad, Synth Pulse, Sub-Bass. Arpeggio chạy Đô3–Đô6. Pad giữ hai nốt Si♭2–Sol♯4 suốt ô nhịp. Pulse cần cả cú chặn ở Đô2 và dải Đô5–Mi6. Chuông là một nốt Đô6–Sol6.

### Mallet

| Vai | Nhạc cụ | Giọng MuseSounds |
|---|---|---|
| P5 | Crotales | Crotales |
| P1 | Marimba | Marimba |
| P2 | Hợp xướng | Full Choir |
| P3 | Harpsichord | Harpsichord |
| P4 | Electric Bass | Electric Bass |

### Guitar và dây

| Vai | Nhạc cụ | Giọng MuseSounds |
|---|---|---|
| P5 | Flute 2 | Flute 2 |
| P1 | Guitar thép | Acoustic Steel Plucked |
| P2 | Cello | Cellos |
| P3 | Piano đứng | Upright Piano |
| P4 | Electric Bass | Electric Bass |

Marimba và guitar thép gánh ostinato. Harpsichord và piano đứng gánh pulse vì phải xuống tới Đô2. Full Choir và Cellos giữ pad suốt ô nhịp. Crotales và Flute 2 chỉ điểm ở Đô6–Sol6.

## Ambient

Bộ đang phát: Celesta, Alto Flute, Bass Flute, French Horn, Contrabasses. Kính ngân ở Sol3–Đô6 và lắng bằng diminuendo. Halo là hai nốt Rê3–Đô♯4. Tiếng nở có đỉnh trong Đô4–La4; đáy lấy từ khoảng dưới đỉnh và có thể xuống La2. Drone theo gốc hợp âm trong Đô2–Si2, ghim chủ âm ở đoạn giữa, và thêm quãng 5 tới Fa♯3 khi thanh khoản `mf`–`f` ở ngoài đoạn giữa. Sau dịch giọng, gốc vang từ La1 tới Rê3 và quãng 5 có thể tới La3. Shimmer là một nốt tròn Rê5–Đô6.

### Hơi trầm

| Vai | Nhạc cụ | Giọng MuseSounds |
|---|---|---|
| P5 | Handchimes | Handchimes |
| P1 | Cor anglais | English Horn |
| P2 | Bass clarinet | Bass Clarinet |
| P3 | Ba trombone | Trombones a3 |
| P4 | Contrabassoon | Contrabassoon |

### Hợp xướng

| Vai | Nhạc cụ | Giọng MuseSounds |
|---|---|---|
| P5 | Handbells | Handbells |
| P1 | Clarinet | Clarinet in Bb |
| P2 | Giọng tenor | Tenors |
| P3 | Viola | Violas |
| P4 | Giọng bass | Basses |

Handchimes và Handbells ngân hết nốt tròn, khác Celesta. Clarinet phủ Sol3–Đô6. Cor anglais giữ hơi kính tới Đô6: Si5–Đô6 chỉ cao hơn trần thường một đến hai nửa cung, nên vẫn để trên kèn. Bass clarinet và tenor giữ halo. Trombones a3 nở được hợp âm kể cả đáy La2. Viola nở cùng vùng đó; đáy giữ ở Đô3 sau khi dịch giọng, vì dây trầm nhất của viola là Đô3. Contrabassoon chơi đủ drone đã dịch, kể cả La1, và giữ cách viết bass hiện tại. Basses viết đúng cao độ vang, không kèm `<octave-change>-1` của part bass. Nốt dưới Đô2 gập lên một quãng tám; Đô2 giữ lại.

## Giọng xuất hiện ở hơn một kiểu

Cùng một giọng MuseSounds có thể đứng ở hai kiểu vì bài không phát chồng. Vai viết thì khác:

| Giọng | Chỗ dùng |
|---|---|
| Trumpet, Trombone | Giai điệu và bè giữa của Jazz Soul; giai điệu và bè giữa của Giao hưởng Đồng |
| Contrabassoon | Bass của Giao hưởng Gỗ; drone của Ambient Hơi trầm |
| Clarinet in Bb | Bè giữa của Giao hưởng Gỗ; kính của Ambient Hợp xướng |
| Cellos | Bè giữa của Giao hưởng hiện tại; pad của Tối giản Guitar và dây |
| Electric Bass | Bass của Giao hưởng hiện tại, của cả hai bộ Jazz, và của cả hai bộ Tối giản |
