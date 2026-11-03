# Soạn trước chương: hàng đợi render cho bản nhiều chương

> **Trạng thái**: P0 và P1 đã vào code trong PR này. P2 (ưu tiên slot, `prepare`, depth > 1) chưa làm, đúng điều kiện trong tài liệu.
> **Phạm vi**: `1M`, `3M`, `1Y` ở phòng Replay (Musicalize). `1D` và `1W` là một chương, không đổi.
> **Không đổi**: form, nhịp, tempo, số ô, chỗ nghỉ, nội dung âm nhạc.
> **Revision**: không bump `SPAN_REVISION`. Field mới là chẩn đoán, additive, thiếu thì mặc định 0; sửa comment ở `audio.py:44-46` để ghi rõ ngoại lệ này (mục 6.5).
> **Thay cho**: cơ chế prefetch một chương trong `src/musicalize/ReplayRoom.tsx` (đợt `12fe5f7`, `a207916`, `82478ad`).

Mục tiêu: **soạn trước theo mức cam kết của người nghe**, để biên chương không phải chờ. Sau review, thứ tự ưu tiên đổi lại: sửa lỗi retry / pause / nghỉ / tranh slot trước; **độ sâu hàng đợi mặc định là 1**, chỉ tăng sau khi có số đo `renderRatio` và có ưu tiên phía server.

---

## 1. Việc đang chạy hôm nay

Luồng của một lượt nghe `1M`, `3M`, `1Y`:

1. Bấm Nghe → `listen()` gọi `fetchSpan` (`src/api/client.ts:647`). Endpoint `/span` chỉ **lập kế hoạch**: nhãn chương, số nến, giá, thời lượng, `ready`, `audioUrl` (`backend/app/routers/stocks.py:537-623`). Không soạn file.
2. `ReplayRoom` đặt `index = 0`, `playing = true`, mount `ReplayPlayer` với `audioUrl` của chương 0 (`src/musicalize/ReplayRoom.tsx:1519-1538`).
3. Player tải URL. Server vào `load_movement_audio` → `ensure_movement` → `_render_movement`: dựng score, MuseScore xuất WAV, tô màu, đo peaks, nén m4a (`backend/app/services/spans.py:199`, `backend/app/sonify/audio.py:1292-1326`, `1328-1429`). Chỉ khi file xong mới có tiếng.
4. Player báo `onDuration`; `mediaIndex.current = index`, `mediaDuration > 0` (`ReplayRoom.tsx:1532`). **Chỉ lúc này** effect prefetch mới được phép chạy.
5. Effect prefetch lấy `index + 1`, gửi Range `bytes=0-0` (`ReplayRoom.tsx:545-574`, `src/api/client.ts:696`).
6. Hết chương, `onEnded` mở hàng nghỉ 6s/8s (`ReplayRoom.tsx:658-688`), rồi tăng `index`. Nếu file chương kế chưa có, player rơi lại vào bước 3.

Cơ chế ở bước 5 là **một chương, một lần, có điều kiện**. Các mục dưới đây là chỗ nó gãy.

---

## 2. Nguyên nhân thật

### 2.1. Prefetch không retry

`prefetchSpanAudio` trả `false`/ném lỗi; effect chỉ chạy lại khi `index`, `mediaDuration`, `playing` hoặc `refreshSpanPeaks` đổi. Một lần 503, timeout hay mất mạng là chương đó **hết prefetch cho tới biên chương**. Đây là nguyên nhân chính tạo ra cảm giác "nghe hết chương rồi mới soạn".

### 2.2. Pause làm hàng đợi đứng

Điều kiện `!playing` chặn mọi prefetch mới khi tạm dừng. Pause là lúc rảnh nhất để soạn tiếp, nhưng hiện tại lại là lúc không có gì chạy.

### 2.3. Nghỉ giữa chương làm mất đồng hồ

Trong lúc nghỉ, `audioUrl` bị đặt về `null` (`ReplayRoom.tsx:1276-1283`), `ReplayPlayer` unmount, `mediaDuration` về 0. Prefetch mới không thể bắt đầu trong 4–8 giây nghỉ. Nghỉ không dùng được để bù thời gian soạn.

### 2.4. Một slot MuseScore, nhiều người nghe

`EXPORT_SLOTS` mặc định 1 (`backend/app/sonify/audio.py:49`), mọi render đi qua `self._slots` (`audio.py:1068`, `1317`). Một prefetch của người này có thể xếp trước request chương đang cần nghe của người khác. Hiện không có ưu tiên phía server. Xem mục 6.4.

### 2.5. Prefetch bắt đầu trễ

Chỉ chạy sau khi chương hiện tại đã tải xong. Độ trễ này chỉ vài giây, **không phải** nguyên nhân chính; sửa nó ở P0 bằng một điều kiện nhỏ (mục 5.5), không cần tăng độ sâu.

### 2.6. Độ sâu 1 có đủ không?

Không có số đo thật trong repo. Ví dụ log ở mục 3 là **định dạng**, không phải số đo. Nếu `renderRatio` thực tế quanh 0,15 như ví dụ đó, depth 1 đã dư 5–6 lần cho chương 8:20. Vì vậy **không mặc định depth 2–3** trước khi đo. Tăng depth là cách xử lý tranh slot, không phải cách xử lý render chậm.

Bảng độ dài để tham chiếu:

| Range | Số chương | Độ dài mỗi chương | Nghỉ |
|---|---|---|---|
| `1M` | 4 | ~3:22–4:30 (manifest guitar 202,5s; giao hưởng ~4:00–4:30) | 6s |
| `3M` | 3 | ~5:26–8:39 (manifest guitar 322,5–516s; giao hưởng ~8:00) | 8s |
| `1Y` | 12 | ~3:07–4:30 | 4s trong mùa, 8s đổi mùa |

Số trong ngoặc lấy từ manifest trong `backend/var/audio/spans`; form gốc ở [`docs/sonify-long-form.md`](./sonify-long-form.md).

### 2.7. Chương đầu vẫn luôn phải chờ

Không có file thì không có tiếng. Prefetch không sửa được chương 0. Đợt này **không** prewarm; ghi nhận là chi phí cố định một lần cho mỗi tác phẩm.

---

## 3. Số phải đo trước khi chọn ngưỡng

Thêm log trong `_render_movement`, đo **từ sau khi đã vào slot** (hàm này được gọi bên trong `with self._slots`, `audio.py:1317-1325`) tới lúc publish xong:

```
span_render symbol=ACB span=3M index=1 musical=<s> export=<s> color=<s>
  peaks=<s> encode=<s> total=<s> ratio=<total/musical>
```

Đây là ví dụ định dạng, **không phải số đo**. `musical` lấy từ `piece_seconds(...)` đã có (`audio.py:1376`).

Ghi vào JSON movement (`audio.py:1404-1425`):

- `renderSec`: tổng giây trong slot.
- `renderRatio`: `renderSec / musical`, guard `musical <= 0 → 0`.

Phía client:

- Dùng `renderRatio` server trả về. **Không** dùng wall time của client để tăng depth, vì wall time gồm cả chờ slot; server bận sẽ đẩy depth lên, tạo vòng lặp dương tính.
- Wall time client chỉ ghi thành `readyLatencySec` để chẩn đoán.
- Chưa có số → `renderRatio = 0` → depth 1.
- Ngưỡng tạm: `ratio > 0.7` mới cho depth 2, và chỉ khi đã có ưu tiên server (mục 6.4).

Lưu ý: `fetch_ohlc` đã có cache 45 giây (`backend/app/services/sessions.py:28`, `40-61`). Vì render tuần tự cách nhau hàng chục giây tới vài phút, cache đó thường hết hạn giữa hai chương. Đây là lý do thật khiến mỗi request phải tải lại OHLC, không phải "không có cache".

---

## 4. Nguyên tắc

1. **Player là chủ sở hữu chương hiện tại.** Pump không bao giờ request `index`. Nếu chương hiện tại chưa có file, chính `ReplayPlayer` đã request nó; pump chen vào chỉ tạo hai request tranh nhau và có thể xếp trước request của player.
2. **Pump chỉ đi trước.** `queueTargets` trả các index `index+1 … index+depth`, không trả `index`.
3. **Ngưỡng cam kết quyết định độ sâu, không quyết định việc bắt đầu.** Chương kế vẫn được soạn ngay khi chương hiện tại bắt đầu phát. Ngưỡng chỉ mở rộng lookahead.
4. **Cam kết tính bằng thời gian đã nghe thật.** `audible` trong code là "đã từng nghe trong chương" (set `true` ở `ReplayRoom.tsx:1530`, chỉ reset khi đổi chương/nghỉ, **không** reset khi pause). `heardSec` là `movementTime`. Pause không làm mất cam kết.
5. **Pause và nghỉ không dừng hàng đợi**, nhưng phải có trần và ưu tiên thấp.
6. **Một request cho một file.** Key theo `audioUrl` (đã chứa fingerprint + số nến), không theo index.
7. **Generation là state thật**, không chỉ ref. Mọi kết quả async phải khớp generation trước khi ghi.
8. **Lỗi tạm thời không giết hàng đợi.** Chương lỗi vào cooldown có thời hạn; chương khác vẫn chạy.
9. **Tranh slot phải có ưu tiên server trước khi tăng depth.** Không tăng tải khi chưa có cơ chế nhường slot.
10. **Mọi việc gắn với URL/fingerprint.** Plan có thể đổi giữa hai lần refresh; `ready` của fingerprint cũ không được gán cho movement mới.

---

## 5. Thiết kế client

### 5.1. Trạng thái

Thay `prefetched: Set<string>` + `prefetchInFlight: Map<number, AbortController>` bằng:

```ts
type QueueState = {
  generation: number;        // mirror của state, dùng cho check async
  inFlight: { index: number; url: string; controller: AbortController } | null;
  attempts: Map<string, number>;            // url → số lần đã thử
  cooldownUntil: Map<number, { url: string; until: number }>;  // index → hết hạn
  done: Set<string>;                        // url đã render xong trong generation này
  renderRatio: number;                      // lấy từ server, không phải wall time
  readyLatencySec: number;                  // chỉ để log
};
```

Ngoài ref, giữ `const [generation, setGeneration] = useState(0)`. `resetPeaksState` (`ReplayRoom.tsx:215`) làm cả hai:

```ts
queue.current.generation += 1;
setGeneration(queue.current.generation);
queue.current.inFlight?.controller.abort();
queue.current.inFlight = null;
queue.current.attempts.clear();
queue.current.cooldownUntil.clear();
queue.current.done.clear();
```

`finishedRef` và `playingRef` là mirror của state, dùng trong vòng bơm. `indexRef` và `movementsRef` đã có (`ReplayRoom.tsx:191-196`).

Lý do phải là state: bấm **Nghe lại cùng mã** không đổi `spanKey`, `hasMovements` vẫn `true`. Nếu generation chỉ là ref, effect không restart, pump cũ thoát vì lệch generation, và không có pump mới.

`renderRatio` khởi tạo từ `renderRatio` lớn nhất mà plan trả về cho các chương đã có file; cập nhật lại mỗi lần `/span/peaks` trả số mới (mục 6.2).

### 5.2. Hàm thuần, có test

Đặt trong `src/musicalize/composeQueue.ts`, test ở `composeQueue.test.ts`. Thêm file test vào danh sách cứng `test:musicalize` (`package.json:51`). `prefetchPlan.test.ts` nằm ở `test:api`, không phải `test:musicalize`.

```ts
export const COMMIT_SEC = 20;
export const COMMIT_RATIO = 0.08;
export const MAX_AHEAD_HARD = 3;   // trần cứng
export const AHEAD_CAP = 1;        // nâng lên 2/3 sau khi có ưu tiên server (6.4)

/** Đã cam kết nghe tiếp chưa. `audible` = đã từng nghe trong chương. */
export function commitReason(input: {
  audible: boolean;
  heardSec: number;
  movementSec: number;
  seeked: boolean;
}): 'seek' | 'dwell' | 'ratio' | null;

/** Số chương đi trước, luôn ≥ 1 và ≤ max. */
export function lookaheadDepth(input: {
  ratio: number;       // renderRatio từ server
  paused: boolean;
  committed: boolean;  // đã nghe đủ ngưỡng cam kết
  max?: number;
}): number;

/** Chỉ trả index > currentIndex. Không bao giờ trả chương hiện tại. */
export function queueTargets(input: {
  currentIndex: number;
  count: number;
  urls: string[];                 // movements[i].audioUrl
  ready: boolean[];
  depth: number;
  done: ReadonlySet<string>;
  cooldownUntil: ReadonlyMap<number, { url: string; until: number }>;
  now: number;
}): number[];

/** Huỷ render đã lùi lại phía sau chương đang nghe. */
export function shouldAbortTarget(target: number | null, currentIndex: number): boolean;

/** Backoff cho lần lỗi thứ `attempt`. */
export function retryDelay(attempt: number): number;

/** Ghi ready cho đúng URL đang có; URL khác thì no-op. renderSec = 0 nghĩa là chưa biết. */
export function markMovementReady<M extends { audioUrl: string; ready: boolean; renderSec?: number }>(
  movements: M[],
  index: number,
  url: string,
  renderSec: number,
): M[];
```

Quy tắc:

- `commitReason`: `seeked` → `'seek'`; `heardSec >= COMMIT_SEC` → `'dwell'`; `movementSec > 0 && heardSec / movementSec >= COMMIT_RATIO` → `'ratio'`; còn lại `null`. Chỉ xét khi `audible`.
- `lookaheadDepth`: chưa cam kết → 1. Đã cam kết: `base = ratio > 0.7 ? 2 : 1`; `paused` thì `base + 1`; kẹp `[1, max]`, `max` mặc định `AHEAD_CAP` và không vượt `MAX_AHEAD_HARD`. Ở P1 `AHEAD_CAP = 1`, nên pause vẫn chỉ đi trước 1 chương. **Không** dùng wall time.
- `queueTargets`: chỉ xét cửa sổ `currentIndex + 1 … currentIndex + depth`; bỏ `ready[i]`, bỏ `done.has(urls[i])`, bỏ index đang cooldown với đúng URL đó. Khi một chương trong cửa sổ đã ready, **không** trượt sang chương sau để lấp chỗ: làm vậy depth 1 sẽ render dần cả tác phẩm. Không chèn `currentIndex`.
- `shouldAbortTarget`: `target != null && target < currentIndex`. `target === currentIndex` **không** huỷ.
- `retryDelay`: 2s, 5s, 10s; sau đó trả 0 (nghĩa là vào cooldown 60 giây, không phải bỏ vĩnh viễn).
- `markMovementReady`: kiểm `movements[index].audioUrl === url`; lệch thì trả nguyên mảng. Khớp thì trả mảng mới chỉ đổi `ready`, và chỉ ghi `renderSec` khi tham số > 0. Không đụng `durationSec`, `peaks`, `prices`.

Ví dụ test bắt buộc:

- `shouldAbortTarget(1, 3) === true`; `shouldAbortTarget(3, 3) === false`; `shouldAbortTarget(4, 3) === false`; `null → false`.
- `queueTargets` với `currentIndex = 2`, `depth = 3`, `count = 6` → không có `2`; tối đa 3 phần tử.
- `markMovementReady` với URL cũ → mảng giữ nguyên reference.
- `commitReason` với `heardSec = 0`, `audible = true` (vừa pause) → `null`; với `heardSec = 25` → `'dwell'`.

### 5.3. Vòng bơm

Ba effect, tách vai.

**a) Vòng bơm** — chạy suốt lượt nghe. Không restart theo `index`; đọc `indexRef`, `movementsRef`, `committedRef`, `playerStartedRef` ở mỗi vòng.

```ts
useEffect(() => {
  if (span === '1D' || !hasMovements) return;
  const gen = generation;
  let stopped = false;

  void (async () => {
    while (!stopped && gen === queue.current.generation) {
      if (finishedRef.current) {
        await sleep(500);
        continue;
      }
      // Player phải là bên request chương hiện tại trước.
      if (!playerStartedRef.current) {
        await sleep(200);
        continue;
      }
      // StrictMode hoặc effect restart: không mở vòng thứ hai.
      if (queue.current.inFlight) {
        await sleep(200);
        continue;
      }

      const depth = lookaheadDepth({
        ratio: queue.current.renderRatio,
        paused: !playingRef.current,
      });
      const targets = queueTargets({
        currentIndex: indexRef.current,
        count: movementsRef.current?.length ?? 0,
        urls: (movementsRef.current ?? []).map((m) => m.audioUrl),
        ready: (movementsRef.current ?? []).map((m) => m.ready),
        depth,
        done: queue.current.done,
        cooldownUntil: queue.current.cooldownUntil,
        now: Date.now(),
      });
      const next = targets[0];
      if (next == null) {
        await sleep(500);
        continue;
      }

      const url = movementsRef.current?.[next]?.audioUrl;
      if (!url) {
        await sleep(500);
        continue;
      }
      const controller = new AbortController();
      queue.current.inFlight = { index: next, url, controller };
      const started = Date.now();
      const timeoutMs = Math.max(
        15 * 60_000,
        (2 * (movementsRef.current?.[next]?.durationSec ?? 0) + 300) * 1000,
      );
      let outcome: 'ready' | 'retry' | 'fatal';
      try {
        outcome = await prefetchSpanAudio(url, controller.signal, timeoutMs);
      } catch {
        outcome = 'retry';
      } finally {
        if (queue.current.inFlight?.controller === controller) {
          queue.current.inFlight = null;
        }
      }
      if (stopped || gen !== queue.current.generation) return;

      // Người dùng vừa nhảy chương: bỏ lượt, không backoff.
      if (controller.signal.aborted) continue;

      if (outcome === 'ready') {
        const latency = (Date.now() - started) / 1000;
        queue.current.readyLatencySec = latency;   // chỉ log
        queue.current.done.add(url);
        queue.current.attempts.delete(url);
        queue.current.cooldownUntil.delete(next);
        // Wall time không phải renderSec. ready trước; peaks sẽ điền số server.
        setMovements((list) => (list ? markMovementReady(list, next, url, 0) : list));
        refreshSpanPeaks();
        continue;
      }
      if (outcome === 'fatal') {
        queue.current.attempts.delete(url);
        queue.current.cooldownUntil.set(next, { url, until: Date.now() + 60_000 });
        continue;
      }
      const attempt = (queue.current.attempts.get(url) ?? 0) + 1;
      queue.current.attempts.set(url, attempt);
      const delay = retryDelay(attempt);
      if (!delay) {
        // Hết 3 lượt: nghỉ 60 giây rồi thử lại từ đầu, không bỏ vĩnh viễn.
        queue.current.attempts.delete(url);
        queue.current.cooldownUntil.set(next, { url, until: Date.now() + 60_000 });
        continue;
      }
      await sleep(delay);
    }
  })();

  return () => {
    stopped = true;
    queue.current.inFlight?.controller.abort();
    queue.current.inFlight = null;
  };
}, [spanKey, hasMovements, generation]);
```

**b) Ưu tiên khi nhảy chương** — chỉ chạy khi `index` đổi:

```ts
useEffect(() => {
  const flight = queue.current.inFlight;
  if (flight && shouldAbortTarget(flight.index, index)) {
    flight.controller.abort();
    queue.current.inFlight = null;
  }
  // Mọi chương từ đây trở đi có lượt thử mới; không block cứng chương kế.
  for (const [target, entry] of queue.current.cooldownUntil) {
    if (target >= index) queue.current.cooldownUntil.delete(target);
  }
  playerStartedRef.current = false;
}, [index]);
```

**c) Chủ sở hữu chương hiện tại** — bật `playerStartedRef` theo điều kiện ở mục 5.4.

Điểm quan trọng:

- **Không** có `index` trong deps của vòng bơm. Nếu có, mỗi lần chuyển chương sẽ abort request đang bay — đúng cái cần giữ khi chương mới chưa có file.
- `controller.signal.aborted` → `continue` ngay, **không** tăng `attempts`, không backoff. Người dùng đang chờ chương đích không bị đẩy thêm 2–10 giây.
- `try/catch/finally` bắt mọi lỗi mạng. Không có `catch` thì async IIFE reject và vòng bơm chết vĩnh viễn.
- `done` được đánh dấu **trước** khi `continue`, không chờ React render lại `movementsRef`. Nếu chỉ dựa vào `ready` trong state, vòng lặp sẽ request lại đúng chương vừa xong.
- `queue.current.inFlight` là chốt single-flight cho StrictMode và cho effect restart.
- `cooldownUntil` có thời hạn; không có `blocked` vĩnh viễn.
- `markMovementReady` được gọi với `url`, nên nếu plan đổi fingerprint giữa chừng thì no-op.
- `prefetchSpanAudio` đổi chữ ký thành `(path, signal, timeoutMs)` và trả `'ready' | 'retry' | 'fatal'` (`src/api/client.ts:696`). `prefetchOutcome` (`src/api/prefetchPlan.ts`): `2xx` → `ready`; `400/401/403/404/422` → `fatal`; còn lại → `retry`. Cập nhật `src/api/prefetchPlan.test.ts`.
- Timeout tính trong vòng bơm: `max(15 * 60_000, (2 * durationSec + 300) * 1000)`, vì request có thể chờ slot. Không được ngắn hơn `musical * 2 + 60` của server (`audio.py:1382`) cộng allowance chờ slot. Khi timeout, trước khi retry phải hỏi `/span/peaks` xem file đã có chưa; tránh render lại từ đầu.

### 5.4. Chủ sở hữu chương hiện tại

`playerStartedRef` chỉ bật khi một trong bốn điều kiện đúng:

- `movements[index].ready === true` (file đã có; request của player là cache hit, không chiếm slot), hoặc
- `mediaIndex.current === index && mediaDuration > 0` (player đã tải xong **đúng chương hiện tại**; giá trị `mediaDuration` còn sót của chương trước không được tính), hoặc
- `audible === true` (player đã phát được ít nhất một lần trong chương), hoặc
- `resting === true` (đang nghỉ giữa chương; player đã unmount nên không còn tranh request).

Reset về `false` mỗi khi `index` đổi. Nhờ vậy pump không bao giờ gửi `index + 1` trước khi request của player cho `index` tới server, và vẫn soạn tiếp được trong lúc nghỉ.

```ts
useEffect(() => {
  const current = movements?.[index];
  if (!current) return;
  if (
    playerHasStarted({
      ready: current.ready,
      audible,
      resting,
      mediaIndex: mediaIndex.current,
      currentIndex: index,
      mediaDurationSec: mediaDuration,
    })
  ) {
    playerStartedRef.current = true;
  }
}, [audible, index, mediaDuration, movements, resting]);
```

Trường hợp chương hiện tại `ready`: request của player đi qua `_lock(piece)` và trả cache **trước** `with self._slots` (`audio.py:1310-1324`), nên prefetch `index + 1` không thể chặn nó. Đây là lý do điều kiện `ready` là đủ an toàn.

Khi player báo `onDuration`, chương đang nghe chắc chắn đã có file. Code đánh dấu `ready` + `done` cho URL đó ngay (`ReplayRoom.tsx`, callback `onDuration`), để nhãn chương không còn "đang soạn" và pump không bao giờ nhắm lại nó.

### 5.5. Cam kết

- `commitReason` chạy trên `audible`, `movementTime`, `movements[index].durationSec`; lưu vào `committedRef`.
- `audible` là "đã từng nghe trong chương", không phải "đang phát". Pause không reset nó.
- `heardSec = movementTime`. Pause làm nó đứng yên, nên không tự tăng cam kết khi không nghe.
- `onEnded` đặt `setMovementTime(end)` (`ReplayRoom.tsx:672`), nên cuối chương `heardSec` bằng cả chương và có thể commit ngay trước biên. Không sai: người dùng đã nghe hết chương.
- Seek chủ động (`jumpToMovement`, `onWorkScrub`, `onStageRatio`) đặt `committed = true` ngay.
- Đổi identity hoặc Nghe lại: `committed = false`, `attempts`/`done`/`cooldown` rỗng.
- Kết thúc tác phẩm: vòng bơm tạm nghỉ, không chết. Nghe lại đặt `finished = false`; hàng đợi chạy tiếp.

### 5.6. Huỷ và cooldown

- Generation đổi: abort `inFlight`, xoá `attempts`/`done`/`cooldown`, dừng vòng bơm cũ. Đây là chỗ duy nhất huỷ toàn bộ.
- `index` đổi: dùng `shouldAbortOnIndexChange` thay cho chỉ so `target < index`:
  - render đã lùi lại phía sau (`flight.index < index`) → huỷ;
  - render nằm ngoài cửa sổ mới (`flight.index > index + depth`) → huỷ, kể cả khi nhảy lùi về một chương đã ready;
  - chương vừa vào **chưa** ready và render không phải chính chương đó → huỷ để request của player vào slot trước;
  - còn lại giữ.
  Xoá cooldown cho **mọi** `target >= index`; reset `playerStartedRef`.
- `fatal` hoặc hết retry: cooldown 60 giây cho đúng index + URL đó. Hết hạn thì thử lại. Không bao giờ block cứng chương kế.
- Rời phòng: abort, như hiện tại (`ReplayRoom.tsx:253-260`).

---

## 6. Thiết kế server

### 6.1. Đo và trả số

- `_render_movement` đo `started = time.monotonic()` ở đầu hàm (đã nằm trong slot), `render_sec` trước khi publish, ghi `renderSec` + `renderRatio` vào payload JSON (`audio.py:1404-1425`).
- Thêm `render_sec: float = 0.0` và `render_ratio: float = 0.0` vào `SpanAsset` (`audio.py:165-181`).
- `_read_span` đọc `payload.get("renderSec") or 0`, `payload.get("renderRatio") or 0` (`audio.py:1437-1482`).
- `SpanMovementResponse` thêm `renderSec?: number`, `renderRatio?: number` (`stocks.py:575-610`). File cũ → 0.
- Log dòng `span_render ...` một lần mỗi lần render, kèm `total` và `ratio`.

### 6.2. `/span/peaks` trả thêm trạng thái và identity

`SpanPeaksResponse` (`backend/app/schemas.py:217-230`) thêm:

- top-level: `asOf: str | None`.
- mỗi movement: `audioUrl: str`, `ready: bool`, `durationSec: float`, `renderSec: float`, `renderRatio: float`.

Route `get_span_peaks` (`stocks.py:626-700`) đã có `plan` và `ready_movement`, nên chỉ cần điền thêm. Không thêm chi phí đáng kể.

Client (`ReplayRoom.tsx:490-536`) hiện chỉ merge `peaks` vào `spanPeaks`. Phải sửa thêm:

- Không dùng `asOf` để chặn cả response: nếu server roll sang ngày mới trong lúc nghe, chặn theo `asOf` sẽ khoá cả peaks của chương đang nghe. Chỉ merge `ready`/`durationSec`/`renderSec`/`renderRatio` khi `peaks.movements[i].audioUrl === movements[i].audioUrl`; peaks vẫn merge theo index như trước.
- `ready === true` thì thêm URL vào `queue.done` để pump không request lại.
- `renderRatio` cập nhật bằng giá trị lớn nhất trong response, chỉ dùng cho `lookaheadDepth`.

### 6.3. Cache plan

Mỗi request audio hiện gọi `plan_span` (`spans.py:199-209`). Với `1Y`, đó là tải 400 ngày OHLC (`spans.py:56`, `149`) và dựng lại 12 chương, cho **từng** chương.

Thiết kế cache:

- Key: `(symbol, span, variant, ensemble)`.
- Single-flight: hai request đồng thời dùng chung một future.
- TTL theo trạng thái thị trường:
  - `is_market_open() == True` → 60 giây.
  - `is_market_open() == False` → 10 phút.
- Kiểm tra lại lúc **đọc** cache: nếu thị trường đang mở và `plan.as_of < hôm nay`, bỏ entry. Một plan tạo lúc 08:50 với `as_of` hôm qua và TTL 10 phút sẽ không sống qua giờ mở cửa 09:00.
- `fetch_ohlc` bên dưới vẫn có TTL 45 giây, nên phần OHLC có thể cũ tối đa 45 giây; plan tự dựng lại từ payload đó.
- Chỉ dùng trong đường audio/prefetch và `/span/peaks`. `/span` vẫn gọi bản tươi.

Đây là điểm sửa so với bản trước: TTL 15 giây vô dụng vì một render đã dài hơn 15 giây. Cache 10 phút cho dữ liệu đóng mới thật sự cắt được chi phí tuần tự.

- 60 giây trong phiên mở chỉ giúp các request **đồng thời/retry**, không amortize chuỗi prefetch tuần tự (một render đã có thể dài hơn 60 giây). Với `AHEAD_CAP = 1`, mỗi chương chỉ cần một plan nên đây không phải blocker.

Rủi ro còn lại: route audio không nhận `scale`/`candles` từ client; nó tự lập kế hoạch rồi trả file theo fingerprint của plan. Với TTL 60 giây trong phiên mở, file trả về có thể lệch fingerprint so với `audioUrl` client đang giữ trong tối đa một phút. Client **không** đổi `audioUrl` giữa lượt nghe: URL mới chỉ được lấy ở lần bấm Nghe kế tiếp. Vì vậy peaks merge `ready` theo URL và bỏ qua row lệch; đây là giới hạn đã biết, không phải cơ chế tự sửa. Ghi rõ trong test để không nới TTL.

### 6.4. Ưu tiên slot

Đây là điều kiện **bắt buộc** nếu P1 tăng depth lên 2+, và **không cần** nếu giữ depth 1.

Thiết kế tối thiểu:

- Client gửi header `X-Span-Priority: prefetch` cho request prefetch. Request phát bình thường không gửi header (mặc định `playback`).
- Server thay `self._slots` bằng một cổng ưu tiên một chỗ:
  - `playback` được vào trước mọi `prefetch` đang chờ.
  - `prefetch` chỉ vào khi không có `playback` đang chờ. Nếu phải chờ quá 5 giây, trả `503` + `Retry-After` để client backoff, thay vì giữ slot.
  - Nếu một `prefetch` đang giữ slot nhưng chưa gọi `self._exporter`, `playback` đặt cancel event của nó (huỷ rẻ, chưa mất công MuseScore). Nếu đã gọi exporter thì để chạy xong; tối đa một lần render.
- `ensure_movement` nhận thêm `priority: Literal["playback", "prefetch"]`; `load_movement_audio` truyền từ header.
- Test: 10 prefetch đang chờ + 1 playback → playback vào slot đầu tiên; prefetch không chiếm slot khi playback đang chờ.

Nếu chưa làm mục này, P1 giữ `depth = 1` (mục 9). Không tăng tải trước khi có ưu tiên.

### 6.5. `SPAN_REVISION` và comment

Comment hiện tại (`audio.py:44-46`) nói manifest shape đổi thì phải bump. Thêm `renderSec`/`renderRatio` là đổi manifest. Chọn:

- **Không bump**, vì đây là field chẩn đoán additive, thiếu thì mặc định 0, không ảnh hưởng playback; bump sẽ xoá toàn bộ cache 4–10 MB/chương.
- Sửa comment thành:

  > Bump when the score, sound, or a manifest field that changes playback changes. Additive diagnostic fields (`renderSec`, `renderRatio`) are exempt: old JSON defaults them to 0.

Không để code và tài liệu nói ngược nhau.

### 6.6. Endpoint `prepare` (P2)

Chỉ làm khi số đo cho thấy `plan_span` còn đắt sau cache, hoặc khi cần worker nền.

```
POST /v1/stocks/{symbol}/span/prepare
    ?range=1Y&from=3&to=5&variant=symphony&ensemble=classic&humanize=1&color=1
→ 202 { "prepared": [3], "pending": [4,5], "generation": "<hash>" }
```

- POST vì có side effect.
- Lập kế hoạch một lần, render tuần tự trong khoảng.
- `generation` là hash của `(symbol, span, variant, ensemble, humanize, color, asOf, fingerprint[])`; client gửi kèm khi huỷ.
- Worker nền kiểm tra cancel mỗi 0,4 giây như `watch_disconnect` (`spans.py:213-224`), tự hết hạn sau 30 giây không có heartbeat.
- Không dùng endpoint này ở P1.

---

## 7. Tài nguyên

- Mặc định `depth = 1` (`AHEAD_CAP = 1`); trần `MAX_AHEAD_HARD = 3` chỉ dùng khi đã có ưu tiên server. `1Y` không bao giờ bị soạn cả 12 chương.
- File `3M`/`1Y` hiện 4–10 MB mỗi chương.
- Cache giữ **30 ngày** (`AUDIO_MAX_AGE_DAYS`, `audio.py:50`), không phải "chỉ lúc đang nghe". Prefetch sâu làm footprint tăng trên toàn bộ cache, không chỉ trong phiên.
- `prune()` chỉ xoá theo tuổi, không theo dung lượng (`audio.py:1286`). Nếu log cho thấy cache phình, làm LRU theo dung lượng sớm hơn P2; đừng đợi đến khi đầy đĩa.
- Không prefetch khi `span === '1D'`, khi chưa có `movements`, khi đã `finished`, hoặc khi `playerStartedRef` chưa bật.

---

## 8. Giao diện

- `SpanMovement` thêm `renderSec?`, `renderRatio?` (`src/api/client.ts:602-630`); `SpanPeaksManifest` thêm `asOf` và các field per-movement ở mục 6.2.
- `Stage` cần thêm prop `movements`/`nextReady` (hiện chưa có). Trong màn nghỉ, hiện "Đang soạn chương kế" khi chương kế `!ready`; không kéo dài thời gian nghỉ.
- Nhãn chương ở `Controls` (`chapterLabel`, `chapterCount`, `ReplayRoom.tsx:1307-1312`) thêm hậu tố "· đang soạn" khi `current.ready === false`.
- Khi chương sau đã sẵn sàng, không hiện gì thêm.

---

## 9. Triển khai theo đợt

### P0 — sửa lỗi, chưa tăng độ sâu

Mục tiêu: hết "nghe hết chương mới soạn" trong điều kiện một người nghe, không tăng tải server.

1. Log `span_render`; thêm `renderSec`/`renderRatio` vào JSON, `SpanAsset`, `_read_span`, schema `/span`.
2. `prefetchSpanAudio` trả `'ready' | 'retry' | 'fatal'`; thêm retry có backoff; abort không backoff.
3. Cho prefetch chạy khi pause và trong lúc nghỉ. Vẫn giữ điều kiện bắt đầu: `mediaDuration > 0` **hoặc** `movements[index].ready === true` **hoặc** `resting === true` (mục 5.4). Không bỏ điều kiện này ở P0.
4. Đánh dấu `done` ngay trong bộ nhớ; không request lại chương vừa xong.
5. `markMovementReady` theo URL.
6. Generation thành state; abort in-flight khi đổi identity/Nghe lại.
7. Cache plan theo mục 6.3 (10 phút cho dữ liệu đóng, 60 giây cho phiên mở, single-flight).
8. Đo `renderRatio` trên `1M`, `3M`, `1Y`, cache trống, một người nghe.

**Không** thêm depth 2/3 ở P0. Nếu sau P0 mà biên chương vẫn chờ, đó là số đo để quyết định P1, không phải để đoán.

### P1 — hàng đợi đúng, depth 1

1. `composeQueue.ts` + test, thêm vào `test:musicalize`.
2. Vòng bơm + effect ưu tiên (mục 5.3), `playerStartedRef`.
3. Cam kết theo mục 5.5, cooldown theo mục 5.6.
4. `/span/peaks` trả thêm identity/trạng thái; sửa merge (mục 6.2).
5. UI trạng thái ở mục 8.
6. Vẫn `depth = 1`. Nếu `renderRatio > 0.7` đo được, mở depth 2 **chỉ sau khi** mục 6.4 xong.

### P2 — mở rộng có kiểm soát

1. Ưu tiên slot (mục 6.4) nếu chưa làm.
2. `POST /span/prepare` + worker nền.
3. Cho phép `depth = 2` (và 3 khi pause dài) sau khi có ưu tiên và số đo.
4. LRU theo dung lượng nếu cache vượt ngưỡng.
5. Cân nhắc `VSTOCK_MUSESCORE_SLOTS = 2` nếu VM ≥ 4 vCPU; đo CPU/nhiệt trước.

---

## 10. Kiểm thử

### Unit TS

Chạy trong `npm run test:musicalize` (đã thêm `composeQueue.test.ts`).

- `commitReason`: chưa nghe → `null`; `heardSec = 25` → `'dwell'`; seek → `'seek'`; `movementSec = 0` không chia 0; `audible = true` + `heardSec = 0` (vừa pause) → `null`.
- `lookaheadDepth`: `ratio = 0` → 1; chưa cam kết với `max = 3` → 1; `ratio = 0.8`, cam kết, `max = 2` → 2; `ratio = 0.8` với `max` mặc định 1 → 1; `paused` cộng 1 nhưng không vượt `max`.
- `queueTargets`: không trả `currentIndex`; tối đa `depth`; bỏ `ready`, `done`, cooldown đúng URL; cooldown của URL khác không chặn index đó.
- `shouldAbortTarget`: `(1, 3) → true`; `(3, 3) → false`; `(4, 3) → false`; `(null, 3) → false`.
- `retryDelay`: 2/5/10 rồi 0.
- `markMovementReady`: URL khớp → đổi đúng một phần tử; URL lệch → giữ nguyên reference; giữ `durationSec`/`peaks`.
- `prefetchOutcome`: 206/200/204 → `ready`; 400/401/403/404/422 → `fatal`; 429/500/503 → `retry`.

### Python

- `test_span.py`: `/span` trả `renderSec`/`renderRatio` khi JSON có, 0 khi file cũ; `_read_span` đọc đúng.
- `/span/peaks`: có `asOf`, `audioUrl`, `ready`, `durationSec`, `renderSec`; movement chưa render trả `ready=false`.
- Plan cache: hai request audio đồng thời chỉ gọi `fetch_ohlc` một lần (single-flight); đóng cửa dùng lại sau 5 phút (TTL 10 phút); phiên mở hết hạn sau 60 giây; plan tạo trước giờ mở bị bỏ khi thị trường mở; hai `variant` khác nhau không dùng chung.
- `SPAN_REVISION` giữ nguyên; test comment/revision hiện có vẫn xanh.
- Khi có P2: playback vào slot trước 10 prefetch đang chờ; prefetch trả `503` + `Retry-After` khi chờ quá 5 giây; cancel trong 1 giây; heartbeat hết hạn dừng worker.

### Thủ công

| Kịch bản | Kỳ vọng |
|---|---|
| `3M`, cache trống, nghe liên tục | Chờ chương I một lần; biên sau không chờ |
| `1M`, pause 60 giây giữa chương II | Chương III được soạn xong trong lúc pause (depth 1) |
| `1Y`, nghe 25 giây rồi nhảy chương 7 | Pump không request chương 7 (player sở hữu); chương 8 bắt đầu sau khi player khởi động chương 7 |
| `3M`, nghe 10 giây rồi đổi mã | Không còn request render của mã cũ |
| Nghe lại cùng mã sau khi kết thúc | Pump mới chạy; log có request chương 1 |
| Mạng chập chờn ở biên chương | Retry, không rơi về "chờ hết chương"; abort không backoff |
| Đổi `humanize`/`color` giữa chừng | Generation mới; `ready`/`peaks` cũ không ghi vào timeline mới |
| Hai người nghe cùng lúc (P2) | Người bấm play không chờ sau prefetch của người kia quá một lần render |

---

## 11. Không làm trong đợt này

- Không prewarm chương 0 trước khi bấm Nghe.
- Không đổi form, nhịp, tempo, số ô, chỗ nghỉ hay nội dung âm nhạc.
- Không đổi `audioUrl`, tên file, `RECAP_REVISION`.
- Không áp dụng cho phòng Live.
- Không thêm worker/process mới ngoài tiến trình API.
- Không tự tăng `VSTOCK_MUSESCORE_SLOTS` mặc định.
- Không bump `SPAN_REVISION`; chỉ sửa comment theo mục 6.5.

---

## 12. Quyết định đã chốt sau review

1. **Depth mặc định 1.** Chỉ lên 2 khi `renderRatio > 0.7` đo được **và** đã có ưu tiên server. 3 chỉ khi pause dài và vẫn có ưu tiên.
2. **Soạn khi pause:** có, tới trần. Nhưng phải có ưu tiên server; nếu chưa có thì depth vẫn 1.
3. **`1Y`:** chỉ buffer quanh chương đang nghe, không cam kết cả 12 chương.
4. **`Retry-After` + ưu tiên tuyệt đối:** làm trước khi tăng depth. Nếu chưa làm, không tăng depth.
5. **Revision:** không bump; sửa comment để ghi ngoại lệ additive.
6. **Timeout prefetch:** rất dài, không abort khi request đã vào slot; trước khi retry phải kiểm tra `/span/peaks`.
7. **Đo depth:** dùng `renderRatio` server, không dùng wall time client.

---

## 13. Đối chiếu review

| # | Vấn đề | Chỗ xử lý |
|---|---|---|
| A1 | Test `shouldAbortTarget` mâu thuẫn | 5.2, 10 |
| A2 | `queueTargets` trả `depth+1`, tranh request với player | 4.1, 4.2, 5.2, 5.4 |
| A3 | Pump request lại chương vừa ready | 5.1 `done`, 5.3 |
| A4 | Readiness phải theo URL/fingerprint | 5.1, 5.2, 5.3 |
| A5 | Thiếu `try/catch`; abort bị backoff | 5.3 |
| A6 | Generation phải là state | 5.1, 5.3 |
| A7 | TTL plan 15 giây vô dụng | 6.3 |
| A8 | Tranh một slot khi tăng depth | 6.4, 9 |
| A9 | Timeout client có thể abort render trong slot | 5.3 |
| A10 | `renderSec` wall time tạo vòng lặp dương | 3, 5.1, 5.3 |
| A11 | `blocked` vĩnh viễn | 5.1, 5.3, 5.6 |
| A12 | `/span/peaks` chỉ merge peaks | 6.2 |
| A13 | `SPAN_REVISION` mâu thuẫn comment | Header, 6.5 |
| A14 | Thiếu `SpanAsset.render_sec` và `_read_span` | 6.1 |
| A15 | P0 bỏ `mediaDuration` có thể đẩy request chương kế lên trước | 5.4, 9 P0 |
| A16 | P0 "không đổi API" nhưng thêm field | 9 P0 (chỉ thêm field tương thích ngược) |
| B | `audible` là "đã từng nghe", `onEnded`, chia 0, script test, POST, Stage, footprint, prune | 5.5, 5.5, 5.2, 5.2, 6.6, 8, 7 |
| C | Depth 1 có thể đã đủ | 2.6, 9, 12 |
| D | Câu hỏi mở | 12 |

---

## 14. Trạng thái triển khai

P0 và P1 đã vào code trong PR này. P2 chưa làm, đúng điều kiện ở mục 9.

- **P0**: `renderSec`/`renderRatio` trong JSON, `SpanAsset`, `_read_span`, `/span`; `/span/peaks` trả thêm identity/trạng thái; prefetch trả `ready|retry|fatal`, retry có backoff, abort không backoff; prefetch chạy khi pause/nghỉ; `done` theo URL; `markMovementReady` theo URL; generation là state; cache plan theo `plan.as_of`.
- **P1**: `src/musicalize/composeQueue.ts` + test; vòng bơm một request, depth 1; `playerStartedRef`; cooldown 60 giây; nhãn "đang soạn" và dòng "đang soạn chương kế" trong màn nghỉ.
- **Sau review #129**: `playerHasStarted` loại `mediaDuration` cũ bằng `mediaIndex`; `shouldAbortOnIndexChange` huỷ render ngoài cửa sổ khi nhảy lùi; DFI poll chỉ merge `ready` khi URL khớp; plan cache TTL theo giờ mở và tự vô hiệu lúc đọc; `/span/peaks` dùng plan cache; bỏ `asOf` guard; `401/403` là `fatal`.
- **Chưa làm (P2)**: `X-Span-Priority`, `POST /span/prepare`, depth 2/3.
- **Không đổi**: form/nhịp/nghỉ, `audioUrl`, `RECAP_REVISION`, `SPAN_REVISION` (chỉ sửa comment ở `audio.py`).
