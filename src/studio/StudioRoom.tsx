import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Image,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import type { PointerEvent as RNPointerEvent } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { absoluteApiUrl, getApiBaseUrl } from '../api/client';
import { palette, TOUCH_TARGET } from '../musicalize/palette';
import { TopBar, type RoomMode } from '../musicalize/TopBar';
import { type } from '../musicalize/type';
import {
  analyzeStudioImage,
  fetchPublishedSpec,
  fetchPublishedSpecs,
  fetchSentenceExamples,
  deleteStudioUpload,
  fetchStudioAccess,
  previewSentenceSpec,
  publishSentenceSpec,
  requestSentenceAudio,
  rollbackSentenceSpec,
  studioAccessUrl,
  studioAnalyzeUrl,
  studioSentenceUrl,
  studioUploadsUrl,
  uploadStudioImage,
  validateSentenceSpec,
  type StudioAccess,
  type StudioAnalyzeDraft,
  type StudioAnalysisNote,
  type StudioError,
  type StudioPreviewResponse,
  type StudioPublishedSpec,
  type StudioUpload,
  type StudioValidateResponse,
} from './api';
import { resolveAudioUrl } from './protocol';
import { sessionLabel } from './session';
import { studioSessionId } from './sessionStorage';
import {
  DEFAULT_SAMPLE,
  SAMPLES,
  accessReasonLabel,
  accessSummary,
  byteSizeLabel,
  draftJson,
  draftNoteRows,
  examplesToSamples,
  checkSpecText,
  containRect,
  cropForUpload,
  cropHandleAt,
  cropRectBetween,
  cropSizeLabel,
  defaultSampleForPattern,
  describeRequestFailure,
  durationLabel,
  findSample,
  fixtureText as sampleFixtureText,
  fixtureTextForSpec,
  imageSizeError,
  measureLines,
  meterLabel,
  metersForPattern,
  moveCropRect,
  nextPublishedList,
  normalizeCropRect,
  normalizeErrorPath,
  notesLines,
  parseJsonObject,
  patternCatalogHint,
  patternIds,
  patternLabel,
  planLines,
  prefixErrorPaths,
  publishedAtLabel,
  publishedSpecLineage,
  publishedSpecMeta,
  publishedSpecTitle,
  resizeCropRect,
  rollbackLabel,
  sampleText,
  shortId,
  textStats,
  uploadMetaLabel,
  valueLines,
  type CropBounds,
  type CropHandle,
  type CropPoint,
  type CropRect,
  type CropSelection,
  type DisplayRect,
  type PublishedListState,
  type StudioSample,
} from './spec';

type Props = {
  wide: boolean;
  onMode: (mode: RoomMode) => void;
};

type RunAction = 'validate' | 'preview';

type StudioResult =
  | { kind: 'idle' }
  | { kind: 'running'; action: RunAction }
  | { kind: 'validate'; data: StudioValidateResponse; elapsedMs: number }
  | { kind: 'preview'; data: StudioPreviewResponse; elapsedMs: number }
  | {
      kind: 'failure';
      action: RunAction;
      message: string;
      errors: StudioError[];
      /** false only when pre-flight stopped before any request was sent. */
      sent: boolean;
    };

type Selection = {
  key: string;
  pattern: string;
  meter: string;
  title: string;
  id?: string;
};

type PreviewSnapshot = {
  spec: Record<string, unknown>;
  fixture: Record<string, unknown>;
  renderHash: string | null;
};

type AudioState =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | {
      kind: 'ready';
      url: string;
      durationSec: number;
      renderHash: string | null;
      playing: boolean;
    }
  | { kind: 'error'; message: string; errors: StudioError[] };

type PublishState =
  | { kind: 'idle' }
  | { kind: 'running' }
  | {
      kind: 'ok';
      id: string;
      pattern: string;
      meter: string;
      version: number;
    }
  | { kind: 'failure'; message: string; errors: StudioError[] };

type RollbackState =
  | { kind: 'idle' }
  | { kind: 'running'; id: string }
  | {
      kind: 'ok';
      id: string;
      version: number | null;
      rollbackOf: string;
    }
  | { kind: 'failure'; id: string; message: string; errors: StudioError[] };

type CatalogState = {
  loading: boolean;
  source: 'api' | 'fallback';
  note: string | null;
};

type AccessState =
  | { kind: 'loading' }
  | { kind: 'ready'; access: StudioAccess }
  | { kind: 'error'; message: string };

type UploadState =
  | { kind: 'idle' }
  | { kind: 'uploading'; filename: string }
  | { kind: 'deleting'; id: string }
  | { kind: 'ready'; upload: StudioUpload }
  | { kind: 'error'; message: string; errors: StudioError[] };

type AnalyzeState =
  | { kind: 'idle' }
  | { kind: 'running' }
  | { kind: 'ready'; draft: StudioAnalyzeDraft }
  | { kind: 'error'; message: string; errors: StudioError[] };

/** Active pointer gesture on the web crop stage. */
type CropDrag =
  | { kind: 'new'; start: CropPoint }
  | { kind: 'move'; start: CropPoint; origin: CropRect }
  | { kind: 'resize'; start: CropPoint; origin: CropRect; handle: CropHandle };

/** One live drag resolved in source-image pixels. */
function dragCropRect(
  drag: CropDrag,
  point: CropPoint,
  bounds: CropBounds,
): CropRect {
  if (drag.kind === 'new') return cropRectBetween(drag.start, point, bounds);
  const dx = point.x - drag.start.x;
  const dy = point.y - drag.start.y;
  if (drag.kind === 'move') return moveCropRect(drag.origin, dx, dy, bounds);
  return resizeCropRect(drag.origin, drag.handle, dx, dy, bounds);
}

/** Placement of a source-pixel crop inside the displayed image box. */
function cropDisplayBox(
  rect: CropRect,
  bounds: CropBounds,
  display: DisplayRect,
): DisplayRect {
  const scaleX = display.width / Math.max(1, bounds.width);
  const scaleY = display.height / Math.max(1, bounds.height);
  return {
    left: rect.x * scaleX,
    top: rect.y * scaleY,
    width: rect.w * scaleX,
    height: rect.h * scaleY,
  };
}

const CONFIDENCE_COLOR = {
  high: palette.data,
  medium: palette.playhead,
  low: palette.sound,
  unknown: palette.textFaint,
} as const;

/** Resolve the relative media URL the upload/analyze endpoints may return. */
function mediaUrl(raw: string | null): string | null {
  if (!raw) return null;
  if (/^(https?:|blob:|data:)/i.test(raw)) return raw;
  return absoluteApiUrl(raw);
}

/**
 * Media elements cannot send `X-Studio-Session`, so the upload response also
 * carries a short-lived token. Append it when the server did not bake it into
 * the URL already.
 */
function uploadImageUri(upload: StudioUpload | null): string | null {
  const base = mediaUrl(upload?.url ?? null);
  if (!base) return null;
  if (!upload?.token || /[?&]t=/.test(base)) return base;
  return `${base}${base.includes('?') ? '&' : '?'}t=${encodeURIComponent(upload.token)}`;
}

const DEFAULT_STUDIO_SAMPLE = DEFAULT_SAMPLE;
const DEFAULT_SELECTION: Selection = {
  key: DEFAULT_STUDIO_SAMPLE.key,
  pattern: DEFAULT_STUDIO_SAMPLE.pattern,
  meter: DEFAULT_STUDIO_SAMPLE.meter,
  title: DEFAULT_STUDIO_SAMPLE.title,
  id: DEFAULT_STUDIO_SAMPLE.id,
};

function msLabel(ms: number): string {
  return `${Math.max(1, Math.round(ms))} ms`;
}

function selectionForSample(sample: StudioSample): Selection {
  return {
    key: sample.key,
    pattern: sample.pattern,
    meter: sample.meter,
    title: sample.title,
    id: sample.id,
  };
}

export function StudioRoom({ wide, onMode }: Props) {
  const insets = useSafeAreaInsets();
  const [samples, setSamples] = useState<readonly StudioSample[]>(SAMPLES);
  const [catalog, setCatalog] = useState<CatalogState>({
    loading: true,
    source: 'fallback',
    note: null,
  });
  const [selection, setSelection] = useState<Selection>(DEFAULT_SELECTION);
  const [specText, setSpecText] = useState(() => sampleText(DEFAULT_STUDIO_SAMPLE));
  const [fixtureJson, setFixtureJson] = useState(() =>
    sampleFixtureText(DEFAULT_STUDIO_SAMPLE),
  );
  const [showFixture, setShowFixture] = useState(false);
  const [result, setResult] = useState<StudioResult>({ kind: 'idle' });
  const [dirty, setDirty] = useState(false);
  const [previewSnapshot, setPreviewSnapshot] = useState<PreviewSnapshot | null>(null);
  const [audio, setAudio] = useState<AudioState>({ kind: 'idle' });
  const [publishState, setPublishState] = useState<PublishState>({ kind: 'idle' });
  const [published, setPublished] = useState<PublishedListState>({
    loading: true,
    items: [],
    error: null,
  });
  const [loadingSpecId, setLoadingSpecId] = useState<string | null>(null);
  const [rollbackState, setRollbackState] = useState<RollbackState>({ kind: 'idle' });
  const [confirmingRollbackId, setConfirmingRollbackId] = useState<string | null>(null);
  const [access, setAccess] = useState<AccessState>({ kind: 'loading' });
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedPreview, setSelectedPreview] = useState<string | null>(null);
  const [upload, setUpload] = useState<UploadState>({ kind: 'idle' });
  const [draftState, setDraftState] = useState<AnalyzeState>({ kind: 'idle' });
  const [showDraftJson, setShowDraftJson] = useState(false);
  const [copyNote, setCopyNote] = useState<string | null>(null);
  const [crop, setCrop] = useState<CropSelection | null>(null);
  const [cropPreview, setCropPreview] = useState<CropRect | null>(null);
  const [cropDrag, setCropDrag] = useState<CropDrag | null>(null);
  const [cropBounds, setCropBounds] = useState<CropBounds | null>(null);
  const [cropStage, setCropStage] = useState<CropBounds>({ width: 0, height: 0 });

  // The server URL wins once the upload succeeds, but the local blob preview
  // covers the gap while the multipart request is in flight.
  const uploaded = upload.kind === 'ready' ? upload.upload : null;
  const previewUri = uploadImageUri(uploaded) ?? selectedPreview;
  const imageBounds = useMemo(
    () =>
      cropBounds ??
      (uploaded?.width && uploaded.height
        ? { width: uploaded.width, height: uploaded.height }
        : null),
    [cropBounds, uploaded?.height, uploaded?.width],
  );
  const activeCrop = cropForUpload(crop, uploaded?.id ?? null);
  const imageDisplay =
    imageBounds && cropStage.width > 0 && cropStage.height > 0
      ? containRect(imageBounds, cropStage)
      : null;
  const visibleCrop = cropPreview ?? activeCrop;
  const cropBox =
    visibleCrop && imageBounds && imageDisplay
      ? cropDisplayBox(visibleCrop, imageBounds, imageDisplay)
      : null;
  const cropReady =
    Platform.OS === 'web' && uploaded !== null && previewUri !== null && imageBounds !== null;

  const inFlight = useRef<AbortController | null>(null);
  const examplesController = useRef<AbortController | null>(null);
  const specsController = useRef<AbortController | null>(null);
  const publishController = useRef<AbortController | null>(null);
  const specDetailController = useRef<AbortController | null>(null);
  const rollbackController = useRef<AbortController | null>(null);
  const audioController = useRef<AbortController | null>(null);
  const accessController = useRef<AbortController | null>(null);
  const uploadController = useRef<AbortController | null>(null);
  const analyzeController = useRef<AbortController | null>(null);
  // The upload an in-flight analyze belongs to; a new file invalidates it.
  const uploadIdRef = useRef<string | null>(null);
  const previewUrlRef = useRef<string | null>(null);
  const cropSurfaceRef = useRef<React.ComponentRef<typeof View> | null>(null);
  const audioPlayer = useRef<HTMLAudioElement | null>(null);
  const audioRunId = useRef(0);
  const runId = useRef(0);
  const specTextRef = useRef(specText);
  const fixtureJsonRef = useRef(fixtureJson);
  const dirtyRef = useRef(dirty);
  const selectionRef = useRef(selection);
  // A run/publish started before the examples response lands must not be wiped
  // by the palette swap.
  const engagedRef = useRef(false);
  specTextRef.current = specText;
  fixtureJsonRef.current = fixtureJson;
  dirtyRef.current = dirty;
  selectionRef.current = selection;

  const stopPlayer = useCallback(() => {
    const player = audioPlayer.current;
    audioPlayer.current = null;
    if (player) {
      try {
        player.pause();
        player.currentTime = 0;
      } catch {
        // The element may already be detached; nothing to release.
      }
    }
  }, []);

  const resetAudio = useCallback(() => {
    audioRunId.current += 1;
    audioController.current?.abort();
    audioController.current = null;
    stopPlayer();
    setAudio({ kind: 'idle' });
  }, [stopPlayer]);

  const applyEditor = useCallback(
    (nextSpecText: string, nextFixtureText: string, nextSelection: Selection) => {
      inFlight.current?.abort();
      inFlight.current = null;
      runId.current += 1;
      resetAudio();
      setSelection(nextSelection);
      setSpecText(nextSpecText);
      setFixtureJson(nextFixtureText);
      setResult({ kind: 'idle' });
      setPreviewSnapshot(null);
      setDirty(false);
    },
    [resetAudio],
  );

  const applySample = useCallback(
    (sample: StudioSample) => {
      applyEditor(sampleText(sample), sampleFixtureText(sample), selectionForSample(sample));
    },
    [applyEditor],
  );

  useEffect(
    () => () => {
      inFlight.current?.abort();
      examplesController.current?.abort();
      specsController.current?.abort();
      publishController.current?.abort();
      specDetailController.current?.abort();
      rollbackController.current?.abort();
      audioController.current?.abort();
      accessController.current?.abort();
      uploadController.current?.abort();
      analyzeController.current?.abort();
      if (
        previewUrlRef.current &&
        typeof URL !== 'undefined' &&
        typeof URL.revokeObjectURL === 'function'
      ) {
        try {
          URL.revokeObjectURL(previewUrlRef.current);
        } catch {
          // The blob URL may already be gone.
        }
        previewUrlRef.current = null;
      }
      stopPlayer();
    },
    [stopPlayer],
  );

  // Capability gate + quota. The editor keeps working if this fails; only the
  // upload/analyze panel depends on `enabled`.
  useEffect(() => {
    const controller = new AbortController();
    accessController.current = controller;
    void (async () => {
      try {
        const next = await fetchStudioAccess(controller.signal);
        if (controller.signal.aborted) return;
        setAccess({ kind: 'ready', access: next });
      } catch (error) {
        if (controller.signal.aborted) return;
        setAccess({ kind: 'error', message: describeRequestFailure(error) });
      } finally {
        if (accessController.current === controller) accessController.current = null;
      }
    })();
    return () => controller.abort();
  }, []);

  // One session id per install/browser. The panel shows a short form so a
  // support report can name the namespace without leaking the full token.
  useEffect(() => {
    let alive = true;
    void studioSessionId()
      .then((id) => {
        if (alive) setSessionId(id);
      })
      .catch(() => {
        if (alive) setSessionId(null);
      });
    return () => {
      alive = false;
    };
  }, []);

  // A different upload (or a local → server URL swap) starts with no crop, and
  // the pixel bounds are re-read so a stale rectangle cannot outlive the image.
  useEffect(() => {
    setCrop(null);
    setCropPreview(null);
    setCropDrag(null);
    setCropBounds(null);
    if (!previewUri || Platform.OS !== 'web') return;
    let alive = true;
    Image.getSize(
      previewUri,
      (width, height) => {
        if (alive && width > 0 && height > 0) setCropBounds({ width, height });
      },
      () => {
        // The upload response's width/height is the fallback; the preview still
        // renders even when the browser cannot measure it.
      },
    );
    return () => {
      alive = false;
    };
  }, [previewUri]);

  // Stop the browser from scrolling/selecting text while a crop drag is live.
  useEffect(() => {
    if (Platform.OS !== 'web') return;
    const node = cropSurfaceRef.current as unknown as HTMLElement | null;
    if (!node) return;
    node.style.touchAction = 'none';
    node.style.userSelect = 'none';
  }, [cropReady, imageDisplay?.width, imageDisplay?.height]);

  // The API examples are the palette. Embedded Torroba/Sor samples only fill in
  // when the endpoint is missing, so the hand-copied list cannot silently drift.
  useEffect(() => {
    const controller = new AbortController();
    examplesController.current = controller;
    void (async () => {
      try {
        const data = await fetchSentenceExamples(controller.signal);
        if (controller.signal.aborted) return;
        const next = examplesToSamples(data.examples);
        if (!next.length) {
          setCatalog({
            loading: false,
            source: 'fallback',
            note: 'Examples API returned no examples — using the embedded Torroba/Sor samples.',
          });
          return;
        }
        setSamples(next);
        setCatalog({ loading: false, source: 'api', note: null });
        if (!dirtyRef.current && !engagedRef.current) {
          const match =
            findSample(selectionRef.current.pattern, selectionRef.current.meter, next) ??
            next[0];
          applySample(match);
        }
      } catch (error) {
        if (controller.signal.aborted) return;
        setCatalog({
          loading: false,
          source: 'fallback',
          note: `Examples API unavailable (${describeRequestFailure(error)}) — using embedded Torroba/Sor samples.`,
        });
      } finally {
        if (examplesController.current === controller) examplesController.current = null;
      }
    })();
    return () => controller.abort();
  }, [applySample]);

  const loadPublished = useCallback(async () => {
    specsController.current?.abort();
    const controller = new AbortController();
    specsController.current = controller;
    setPublished((prev) => nextPublishedList(prev, { kind: 'start' }));
    try {
      const items = await fetchPublishedSpecs(controller.signal);
      if (controller.signal.aborted) return;
      setPublished((prev) => nextPublishedList(prev, { kind: 'success', items }));
    } catch (error) {
      if (controller.signal.aborted) return;
      setPublished((prev) =>
        nextPublishedList(prev, {
          kind: 'failure',
          message: describeRequestFailure(error),
        }),
      );
    } finally {
      if (specsController.current === controller) specsController.current = null;
    }
  }, []);

  useEffect(() => {
    void loadPublished();
    return () => specsController.current?.abort();
  }, [loadPublished]);

  const choosePattern = useCallback(
    (pattern: string) => {
      const sample =
        findSample(pattern, selection.meter, samples) ??
        defaultSampleForPattern(pattern, samples);
      applySample(sample);
    },
    [applySample, samples, selection.meter],
  );

  const chooseMeter = useCallback(
    (meter: string) => {
      const sample = findSample(selection.pattern, meter, samples);
      if (sample) applySample(sample);
    },
    [applySample, samples, selection.pattern],
  );

  const run = useCallback(
    async (action: RunAction) => {
      engagedRef.current = true;
      const checked = checkSpecText(specText);
      if (!checked.ok) {
        setResult({
          kind: 'failure',
          action,
          message: 'Fix the spec JSON before sending it.',
          errors: checked.errors,
          sent: false,
        });
        return;
      }

      let fixture: Record<string, unknown> | null = null;
      if (action === 'preview') {
        const parsed = parseJsonObject(fixtureJson, 'Fixture');
        if (!parsed.ok) {
          setResult({
            kind: 'failure',
            action,
            message: 'Fix the preview fixture before sending it.',
            errors: prefixErrorPaths(parsed.errors, 'fixture'),
            sent: false,
          });
          return;
        }
        fixture = parsed.value;
      }

      resetAudio();
      setPreviewSnapshot(null);
      inFlight.current?.abort();
      const controller = new AbortController();
      inFlight.current = controller;
      const id = ++runId.current;
      const startedAt = Date.now();
      const startedSpec = specText;
      const startedFixture = fixtureJson;
      setResult({ kind: 'running', action });

      try {
        if (action === 'validate') {
          const data = await validateSentenceSpec(checked.spec, controller.signal);
          if (id !== runId.current) return;
          setResult({ kind: 'validate', data, elapsedMs: Date.now() - startedAt });
        } else {
          const data = await previewSentenceSpec(
            checked.spec,
            fixture as Record<string, unknown>,
            controller.signal,
          );
          if (id !== runId.current) return;
          setResult({ kind: 'preview', data, elapsedMs: Date.now() - startedAt });
          if (data.ok) {
            setPreviewSnapshot({
              spec: checked.spec,
              fixture: fixture ?? {},
              renderHash: data.renderHash,
            });
          }
        }
        if (
          specTextRef.current === startedSpec &&
          fixtureJsonRef.current === startedFixture
        ) {
          setDirty(false);
        }
      } catch (error) {
        if (controller.signal.aborted || id !== runId.current) return;
        setResult({
          kind: 'failure',
          action,
          message: describeRequestFailure(error),
          errors: [],
          sent: true,
        });
      } finally {
        if (inFlight.current === controller) inFlight.current = null;
      }
    },
    [fixtureJson, resetAudio, specText],
  );

  /** Drop any committed or in-progress crop. */
  const resetCrop = useCallback(() => {
    setCrop(null);
    setCropPreview(null);
    setCropDrag(null);
  }, []);

  const cropPointFromClient = useCallback(
    (clientX: number, clientY: number): CropPoint | null => {
      if (!imageBounds) return null;
      const node = cropSurfaceRef.current as unknown as HTMLElement | null;
      if (!node || typeof node.getBoundingClientRect !== 'function') return null;
      const box = node.getBoundingClientRect();
      if (!(box.width > 0) || !(box.height > 0)) return null;
      const scaleX = imageBounds.width / box.width;
      const scaleY = imageBounds.height / box.height;
      return {
        x: Math.min(Math.max((clientX - box.left) * scaleX, 0), imageBounds.width),
        y: Math.min(Math.max((clientY - box.top) * scaleY, 0), imageBounds.height),
      };
    },
    [imageBounds],
  );

  const startCropDrag = useCallback(
    (event: RNPointerEvent) => {
      if (Platform.OS !== 'web' || !imageBounds) return;
      const point = cropPointFromClient(
        event.nativeEvent.clientX,
        event.nativeEvent.clientY,
      );
      if (!point) return;
      event.preventDefault?.();

      const node = cropSurfaceRef.current as unknown as HTMLElement | null;
      const box =
        node && typeof node.getBoundingClientRect === 'function'
          ? node.getBoundingClientRect()
          : null;
      const scale = box && box.width > 0 ? imageBounds.width / box.width : 1;
      // A 10 CSS-pixel corner target in source-image pixels.
      const tolerance = 10 / Math.max(scale, 0.0001);
      const existing = cropForUpload(crop, uploaded?.id ?? null);
      const target = existing ? cropHandleAt(existing, point, tolerance) : null;

      setCropPreview(null);
      if (existing && target === 'inside') {
        setCropDrag({ kind: 'move', start: point, origin: existing });
      } else if (existing && target !== null && target !== 'inside') {
        setCropDrag({
          kind: 'resize',
          start: point,
          origin: existing,
          handle: target,
        });
      } else {
        setCropDrag({ kind: 'new', start: point });
      }
    },
    [crop, cropPointFromClient, imageBounds, uploaded?.id],
  );

  // Pointer moves/ups live on `window` so a drag can leave the image without
  // losing the gesture. Release commits the normalized rectangle.
  useEffect(() => {
    if (Platform.OS !== 'web' || !cropDrag || !imageBounds) return;
    const uploadId = uploaded?.id ?? null;

    const pointFor = (event: PointerEvent): CropPoint | null =>
      cropPointFromClient(event.clientX, event.clientY);

    const onMove = (event: PointerEvent) => {
      const point = pointFor(event);
      if (!point) return;
      event.preventDefault();
      setCropPreview(dragCropRect(cropDrag, point, imageBounds));
    };

    const onUp = (event: PointerEvent) => {
      const point = pointFor(event);
      if (point && uploadId) {
        const normalized = normalizeCropRect(
          dragCropRect(cropDrag, point, imageBounds),
          imageBounds,
        );
        if (normalized) {
          setCrop({ uploadId, rect: normalized });
        } else if (cropDrag.kind === 'new') {
          // A click/tiny drag outside the old crop clears the selection.
          setCrop(null);
        }
      }
      setCropPreview(null);
      setCropDrag(null);
    };

    window.addEventListener('pointermove', onMove, { passive: false });
    window.addEventListener('pointerup', onUp);
    window.addEventListener('pointercancel', onUp);
    return () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
      window.removeEventListener('pointercancel', onUp);
    };
  }, [cropDrag, cropPointFromClient, imageBounds, uploaded?.id]);

  const pickFile = useCallback(
    (file: File | null) => {
      // Replace flow is delete-then-pick; an already-uploaded file must not
      // silently mint a second row/quota charge.
      if (upload.kind === 'ready') return;
      uploadController.current?.abort();
      uploadController.current = null;
      analyzeController.current?.abort();
      analyzeController.current = null;
      uploadIdRef.current = null;
      if (
        previewUrlRef.current &&
        typeof URL !== 'undefined' &&
        typeof URL.revokeObjectURL === 'function'
      ) {
        try {
          URL.revokeObjectURL(previewUrlRef.current);
        } catch {
          // Nothing to release.
        }
        previewUrlRef.current = null;
      }
      setSelectedFile(null);
      setSelectedPreview(null);
      setDraftState({ kind: 'idle' });
      setShowDraftJson(false);
      setCopyNote(null);
      resetCrop();

      if (!file) {
        setUpload({ kind: 'idle' });
        return;
      }
      if (access.kind === 'loading' || (access.kind === 'ready' && !access.access.enabled)) {
        setUpload({
          kind: 'error',
          message:
            access.kind === 'ready'
              ? 'Studio is disabled on this server; the sentence editor still works.'
              : 'Checking Studio access before upload…',
          errors: [],
        });
        return;
      }

      const mime = file.type.toLowerCase();
      if (mime && !mime.startsWith('image/')) {
        setUpload({
          kind: 'error',
          message: `Chỉ nhận file ảnh (${file.type}).`,
          errors: [],
        });
        return;
      }
      const maxMb = access.kind === 'ready' ? access.access.quota.maxImageMb : 0;
      const tooBig = imageSizeError(file.size, maxMb);
      if (tooBig) {
        setUpload({ kind: 'error', message: tooBig, errors: [] });
        return;
      }

      let preview: string | null = null;
      if (typeof URL !== 'undefined' && typeof URL.createObjectURL === 'function') {
        try {
          preview = URL.createObjectURL(file);
          previewUrlRef.current = preview;
        } catch {
          preview = null;
        }
      }
      setSelectedFile(file);
      setSelectedPreview(preview);
      setUpload({ kind: 'idle' });
    },
    [access, resetCrop, upload.kind],
  );

  const uploadSelected = useCallback(async () => {
    if (!selectedFile) return;
    uploadController.current?.abort();
    analyzeController.current?.abort();
    analyzeController.current = null;
    uploadIdRef.current = null;
    const controller = new AbortController();
    uploadController.current = controller;
    setUpload({ kind: 'uploading', filename: selectedFile.name || 'image' });
    setDraftState({ kind: 'idle' });
    setShowDraftJson(false);
    setCopyNote(null);
    resetCrop();
    try {
      const data = await uploadStudioImage(selectedFile, {
        filename: selectedFile.name || undefined,
        signal: controller.signal,
      });
      if (controller.signal.aborted) return;
      if (!data.ok || !data.id) {
        setUpload({
          kind: 'error',
          message: data.errors[0]?.message ?? 'Upload failed.',
          errors: data.errors,
        });
        return;
      }
      uploadIdRef.current = data.id;
      setUpload({ kind: 'ready', upload: data });
    } catch (error) {
      if (controller.signal.aborted) return;
      setUpload({
        kind: 'error',
        message: describeRequestFailure(error),
        errors: [],
      });
    } finally {
      if (uploadController.current === controller) uploadController.current = null;
    }
  }, [resetCrop, selectedFile]);

  const deleteUpload = useCallback(async () => {
    if (upload.kind !== 'ready' || !upload.upload.id) return;
    analyzeController.current?.abort();
    analyzeController.current = null;
    uploadIdRef.current = null;
    uploadController.current?.abort();
    const controller = new AbortController();
    uploadController.current = controller;
    const id = upload.upload.id;
    setUpload({ kind: 'deleting', id });
    resetCrop();
    try {
      const data = await deleteStudioUpload(id, controller.signal);
      if (controller.signal.aborted) return;
      if (!data.ok) {
        setUpload({
          kind: 'error',
          message: data.errors[0]?.message ?? 'Delete failed.',
          errors: data.errors,
        });
        return;
      }
      if (
        previewUrlRef.current &&
        typeof URL !== 'undefined' &&
        typeof URL.revokeObjectURL === 'function'
      ) {
        try {
          URL.revokeObjectURL(previewUrlRef.current);
        } catch {
          // The blob URL may already be gone.
        }
        previewUrlRef.current = null;
      }
      setSelectedFile(null);
      setSelectedPreview(null);
      setUpload({ kind: 'idle' });
      setDraftState({ kind: 'idle' });
      setShowDraftJson(false);
      setCopyNote(null);
    } catch (error) {
      if (controller.signal.aborted) return;
      setUpload({
        kind: 'error',
        message: describeRequestFailure(error),
        errors: [],
      });
    } finally {
      if (uploadController.current === controller) uploadController.current = null;
    }
  }, [resetCrop, upload]);

  const analyzeUpload = useCallback(async () => {
    if (upload.kind !== 'ready' || !upload.upload.id) return;
    const requestedId = upload.upload.id;
    // Re-validate against the current image bounds and drop a rectangle that
    // belongs to another upload. No crop means the whole image.
    const storedCrop = cropForUpload(crop, requestedId);
    const requestedCrop =
      storedCrop && imageBounds
        ? normalizeCropRect(storedCrop, imageBounds)
        : null;
    analyzeController.current?.abort();
    const controller = new AbortController();
    analyzeController.current = controller;
    setDraftState({ kind: 'running' });
    setShowDraftJson(false);
    setCopyNote(null);
    try {
      const draft = await analyzeStudioImage(requestedId, {
        crop: requestedCrop,
        signal: controller.signal,
      });
      if (controller.signal.aborted || uploadIdRef.current !== requestedId) return;
      if (!draft.ok && draft.notes.length === 0 && draft.errors.length > 0) {
        setDraftState({
          kind: 'error',
          message: draft.errors[0]?.message ?? 'Analyze failed.',
          errors: draft.errors,
        });
        return;
      }
      setDraftState({ kind: 'ready', draft });
    } catch (error) {
      if (controller.signal.aborted || uploadIdRef.current !== requestedId) return;
      setDraftState({
        kind: 'error',
        message: describeRequestFailure(error),
        errors: [],
      });
    } finally {
      if (analyzeController.current === controller) analyzeController.current = null;
    }
  }, [crop, imageBounds, upload]);

  const copyDraft = useCallback(async () => {
    if (draftState.kind !== 'ready') return;
    const text = draftJson(draftState.draft);
    try {
      if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
        setCopyNote('Draft JSON copied.');
        return;
      }
    } catch {
      // Fall through to the selectable block.
    }
    setCopyNote('Clipboard unavailable — select the read-only JSON instead.');
    setShowDraftJson(true);
  }, [draftState]);

  const playAudio = useCallback(async () => {
    if (!previewSnapshot) return;
    if (Platform.OS !== 'web') {
      setAudio({
        kind: 'error',
        message: 'Audio playback is web-only in this sprint.',
        errors: [],
      });
      return;
    }

    audioController.current?.abort();
    const controller = new AbortController();
    audioController.current = controller;
    const id = ++audioRunId.current;
    stopPlayer();
    setAudio({ kind: 'loading' });

    try {
      const data = await requestSentenceAudio(
        { spec: previewSnapshot.spec, fixture: previewSnapshot.fixture },
        controller.signal,
      );
      if (controller.signal.aborted || id !== audioRunId.current) return;
      if (!data.ok || !data.audioUrl) {
        setAudio({
          kind: 'error',
          message: data.errors[0]?.message ?? 'Audio preview failed.',
          errors: data.errors,
        });
        return;
      }
      const url = resolveAudioUrl(getApiBaseUrl(), data.audioUrl);
      if (!url) {
        setAudio({
          kind: 'error',
          message: 'The audio response did not include a usable URL.',
          errors: [],
        });
        return;
      }

      const player = new Audio(url);
      audioPlayer.current = player;
      player.onended = () => {
        if (id === audioRunId.current) {
          setAudio((prev) => (prev.kind === 'ready' ? { ...prev, playing: false } : prev));
        }
      };
      player.onerror = () => {
        if (id === audioRunId.current) {
          setAudio({
            kind: 'error',
            message: 'The browser could not play the preview WAV.',
            errors: [],
          });
        }
      };
      await player.play();
      if (controller.signal.aborted || id !== audioRunId.current) {
        player.pause();
        return;
      }
      setAudio({
        kind: 'ready',
        url,
        durationSec: data.durationSec,
        renderHash: data.renderHash ?? previewSnapshot.renderHash,
        playing: true,
      });
    } catch (error) {
      if (controller.signal.aborted || id !== audioRunId.current) return;
      setAudio({
        kind: 'error',
        message: describeRequestFailure(error),
        errors: [],
      });
    } finally {
      if (audioController.current === controller) audioController.current = null;
    }
  }, [previewSnapshot, stopPlayer]);

  const publish = useCallback(async () => {
    engagedRef.current = true;
    const checked = checkSpecText(specTextRef.current);
    if (!checked.ok) {
      setPublishState({
        kind: 'failure',
        message: 'Fix the spec JSON before publishing.',
        errors: checked.errors,
      });
      return;
    }

    publishController.current?.abort();
    const controller = new AbortController();
    publishController.current = controller;
    setPublishState({ kind: 'running' });
    try {
      const data = await publishSentenceSpec(checked.spec, controller.signal);
      if (controller.signal.aborted) return;
      if (!data.ok || !data.id) {
        setPublishState({
          kind: 'failure',
          message: data.errors[0]?.message ?? 'Publish failed.',
          errors: data.errors,
        });
        return;
      }
      setPublishState({
        kind: 'ok',
        id: data.id,
        pattern: data.pattern ?? String(checked.spec.pattern ?? ''),
        meter: data.meter ?? String(checked.spec.meter ?? ''),
        version: data.version ?? 0,
      });
      void loadPublished();
    } catch (error) {
      if (controller.signal.aborted) return;
      setPublishState({
        kind: 'failure',
        message: describeRequestFailure(error),
        errors: [],
      });
    } finally {
      if (publishController.current === controller) publishController.current = null;
    }
  }, [loadPublished]);

  const openPublished = useCallback(
    async (id: string) => {
      specDetailController.current?.abort();
      const controller = new AbortController();
      specDetailController.current = controller;
      setLoadingSpecId(id);
      setPublished((prev) => ({ ...prev, error: null }));
      try {
        const detail = await fetchPublishedSpec(id, controller.signal);
        if (controller.signal.aborted) return;
        applyEditor(
          JSON.stringify(detail.payload, null, 2),
          fixtureTextForSpec(detail.payload),
          {
            key: `${detail.pattern}:${detail.meter}`,
            pattern: detail.pattern,
            meter: detail.meter,
            title: `${publishedSpecTitle(detail)} · v${detail.version}`,
            id: detail.id,
          },
        );
        setPublishState({ kind: 'idle' });
      } catch (error) {
        if (controller.signal.aborted) return;
        setPublished((prev) => ({
          ...prev,
          error: `Could not load ${shortId(id)}: ${describeRequestFailure(error)}`,
        }));
      } finally {
        if (specDetailController.current === controller) {
          specDetailController.current = null;
        }
        setLoadingSpecId((current) => (current === id ? null : current));
      }
    },
    [applyEditor],
  );

  const rollback = useCallback(
    async (id: string) => {
      setConfirmingRollbackId(null);
      rollbackController.current?.abort();
      const controller = new AbortController();
      rollbackController.current = controller;
      setRollbackState({ kind: 'running', id });
      try {
        const data = await rollbackSentenceSpec(id, controller.signal);
        if (controller.signal.aborted) return;
        if (!data.ok || !data.id) {
          setRollbackState({
            kind: 'failure',
            id,
            message: data.errors[0]?.message ?? 'Rollback failed.',
            errors: data.errors,
          });
          return;
        }
        setRollbackState({
          kind: 'ok',
          id: data.id,
          version: data.version,
          rollbackOf: data.rollbackOf ?? id,
        });
        void loadPublished();
      } catch (error) {
        if (controller.signal.aborted) return;
        setRollbackState({
          kind: 'failure',
          id,
          message: describeRequestFailure(error),
          errors: [],
        });
      } finally {
        if (rollbackController.current === controller) {
          rollbackController.current = null;
        }
      }
    },
    [loadPublished],
  );

  const running = result.kind === 'running';
  const publishing = publishState.kind === 'running';
  const stale =
    dirty &&
    (result.kind === 'validate' ||
      result.kind === 'preview' ||
      result.kind === 'failure');
  const stats = textStats(specText);

  const accessLoading = access.kind === 'loading';
  const uploadEnabled =
    access.kind === 'ready' ? access.access.enabled : access.kind === 'error';
  const uploadBusy = upload.kind === 'uploading' || upload.kind === 'deleting';
  const analyzeBusy = draftState.kind === 'running';
  const canUpload =
    uploadEnabled && selectedFile !== null && !uploadBusy && upload.kind !== 'ready';
  const canAnalyze = uploadEnabled && Boolean(uploaded?.id) && !analyzeBusy && !uploadBusy;
  const accessNote =
    access.kind === 'ready'
      ? accessSummary(access.access)
      : access.kind === 'loading'
        ? 'checking Studio access…'
        : `access check failed · ${access.message}`;

  const catalogPatterns = patternIds(samples);
  const patternChoices = catalogPatterns.includes(selection.pattern)
    ? catalogPatterns
    : [selection.pattern, ...catalogPatterns];
  const catalogMeters = metersForPattern(samples, selection.pattern);
  const meterChoices = catalogMeters.includes(selection.meter)
    ? catalogMeters
    : [selection.meter, ...catalogMeters];

  return (
    <View
      style={[
        styles.root,
        { paddingTop: insets.top, paddingBottom: insets.bottom },
      ]}
    >
      <TopBar mode="studio" onMode={onMode} searchEnabled={false} />

      <ScrollView
        contentContainerStyle={styles.scroll}
        keyboardShouldPersistTaps="handled"
      >
        <View style={styles.shell}>
          <View style={styles.header}>
            <View style={styles.eyebrowRow}>
              <Text style={[type.section, styles.eyebrow]}>Studio · sentence JSON</Text>
              <View style={styles.devBadge}>
                <Text style={styles.devBadgeText}>DEV</Text>
              </View>
              <Text numberOfLines={1} style={styles.sessionText}>
                {sessionLabel(sessionId)} · {accessNote}
              </Text>
            </View>
            <Text style={[type.displayNarrow, styles.title]}>Sentence lab</Text>
            <Text style={styles.subtitle}>
              Edit one sentence spec, validate it against the registry, preview the
              plan and render hash, then play the short preview WAV and publish a
              version. The JSON editor remains the source of truth. The image
              panel above is a separate front half: upload a score photo, ask
              Gemini for a TextureSpec note draft, and review it here without
              overwriting the sentence JSON.
            </Text>
          </View>

          <View style={[styles.columns, wide && styles.columnsWide]}>
            <View style={[styles.column, wide && styles.columnWide]}>
              <View style={styles.card}>
                <View style={styles.resultHeader}>
                  <Text style={[type.section, styles.cardLabel]}>Import ảnh</Text>
                  <Text style={styles.actionLabel}>Gemini</Text>
                </View>
                <Text style={styles.cardTitle}>Score photo → draft notes</Text>
                <Text style={styles.hint}>
                  Upload one page (PNG, JPEG, WebP). The server stores it under
                  this session and returns a TextureSpec note draft. It never
                  replaces the SentenceSpec JSON below.
                </Text>

                {access.kind === 'ready' && !access.access.enabled ? (
                  <View style={styles.noticeBox}>
                    <Text style={styles.noticeTitle}>
                      Studio disabled · {accessReasonLabel(access.access.reason)}
                    </Text>
                    <Text style={styles.noticeText}>
                      Upload and Analyze are turned off. The sentence JSON editor
                      below still works.
                    </Text>
                  </View>
                ) : access.kind === 'error' ? (
                  <View style={styles.noticeBox}>
                    <Text style={styles.noticeTitle}>Access check failed</Text>
                    <Text style={styles.noticeText}>
                      {access.message} — upload stays enabled and the server
                      enforces session quota.
                    </Text>
                  </View>
                ) : null}

                {Platform.OS === 'web' ? (
                  <View style={styles.importRow}>
                    {React.createElement('input', {
                      type: 'file',
                      accept: 'image/png,image/jpeg,image/webp',
                      disabled:
                        !uploadEnabled ||
                        uploadBusy ||
                        accessLoading ||
                        upload.kind === 'ready',
                      'aria-label': 'Choose a score image',
                      onChange: (event: React.ChangeEvent<HTMLInputElement>) => {
                        const file = event.target.files?.[0] ?? null;
                        // Reset so choosing the same file after an error fires
                        // onChange again.
                        event.target.value = '';
                        pickFile(file);
                      },
                      style: { color: palette.textMuted, fontSize: 12, maxWidth: '100%' },
                    })}
                    <Text numberOfLines={1} style={styles.fileName}>
                      {selectedFile
                        ? `${selectedFile.name || 'image'} · ${byteSizeLabel(selectedFile.size)}`
                        : 'No file selected'}
                    </Text>
                  </View>
                ) : (
                  <Text style={styles.noticeText}>
                    Image import is web-only in this pass. Use the JSON editor
                    below on native.
                  </Text>
                )}

                {cropReady && previewUri ? (
                  <View
                    onLayout={(event) => {
                      const { width, height } = event.nativeEvent.layout;
                      setCropStage((prev) =>
                        prev.width === width && prev.height === height
                          ? prev
                          : { width, height },
                      );
                    }}
                    style={styles.cropStage}
                  >
                    {imageDisplay && imageDisplay.width > 0 ? (
                      <View
                        ref={cropSurfaceRef}
                        onPointerDown={startCropDrag}
                        accessibilityRole="imagebutton"
                        accessibilityLabel="Crop the score image"
                        accessibilityHint="Drag to draw a rectangle; drag inside to move; drag a corner to resize."
                        style={[
                          styles.cropSurface,
                          {
                            left: imageDisplay.left,
                            top: imageDisplay.top,
                            width: imageDisplay.width,
                            height: imageDisplay.height,
                          },
                        ]}
                      >
                        <Image
                          source={{ uri: previewUri }}
                          style={styles.cropImage}
                          resizeMode="stretch"
                          pointerEvents="none"
                          accessibilityLabel="Selected score image preview"
                        />
                        {visibleCrop && cropBox ? (
                          <>
                            <View
                              pointerEvents="none"
                              style={[
                                styles.cropShade,
                                {
                                  left: 0,
                                  top: 0,
                                  width: imageDisplay.width,
                                  height: cropBox.top,
                                },
                              ]}
                            />
                            <View
                              pointerEvents="none"
                              style={[
                                styles.cropShade,
                                {
                                  left: 0,
                                  top: cropBox.top + cropBox.height,
                                  width: imageDisplay.width,
                                  height: Math.max(
                                    0,
                                    imageDisplay.height - (cropBox.top + cropBox.height),
                                  ),
                                },
                              ]}
                            />
                            <View
                              pointerEvents="none"
                              style={[
                                styles.cropShade,
                                {
                                  left: 0,
                                  top: cropBox.top,
                                  width: cropBox.left,
                                  height: cropBox.height,
                                },
                              ]}
                            />
                            <View
                              pointerEvents="none"
                              style={[
                                styles.cropShade,
                                {
                                  left: cropBox.left + cropBox.width,
                                  top: cropBox.top,
                                  width: Math.max(
                                    0,
                                    imageDisplay.width - (cropBox.left + cropBox.width),
                                  ),
                                  height: cropBox.height,
                                },
                              ]}
                            />
                            <View
                              pointerEvents="none"
                              style={[
                                styles.cropSelection,
                                {
                                  left: cropBox.left,
                                  top: cropBox.top,
                                  width: cropBox.width,
                                  height: cropBox.height,
                                },
                              ]}
                            >
                              <View style={[styles.cropHandle, styles.cropHandleNw]} />
                              <View style={[styles.cropHandle, styles.cropHandleNe]} />
                              <View style={[styles.cropHandle, styles.cropHandleSw]} />
                              <View style={[styles.cropHandle, styles.cropHandleSe]} />
                            </View>
                          </>
                        ) : null}
                      </View>
                    ) : null}
                  </View>
                ) : previewUri ? (
                  <Image
                    source={{ uri: previewUri }}
                    style={styles.imagePreview}
                    resizeMode="contain"
                    accessibilityLabel="Selected score image preview"
                  />
                ) : null}

                {cropReady ? (
                  <View style={styles.cropToolbar}>
                    <Text style={styles.cropMeta}>
                      {activeCrop
                        ? `Crop ${cropSizeLabel(activeCrop)}`
                        : 'Whole image'}
                    </Text>
                    {activeCrop ? (
                      <ActionButton
                        label="Clear crop"
                        onPress={resetCrop}
                        disabled={cropDrag !== null}
                      />
                    ) : null}
                  </View>
                ) : null}
                {previewUri && Platform.OS === 'web' && uploaded ? (
                  <Text style={styles.composerHint}>
                    {activeCrop
                      ? 'Analyze reads only this rectangle. Drag inside to move it, or drag a corner to resize.'
                      : 'Drag on the image to select a staff region. Without a crop, Analyze reads the whole page.'}
                  </Text>
                ) : null}

                <View style={styles.actions}>
                  <ActionButton
                    label="Upload ảnh"
                    primary
                    onPress={() => void uploadSelected()}
                    disabled={!canUpload}
                    busy={uploadBusy}
                  />
                  <ActionButton
                    label="Analyze"
                    onPress={() => void analyzeUpload()}
                    disabled={!canAnalyze}
                    busy={analyzeBusy}
                  />
                  {upload.kind === 'ready' ? (
                    <ActionButton
                      label="Xoá ảnh"
                      onPress={() => void deleteUpload()}
                      disabled={uploadBusy || analyzeBusy}
                    />
                  ) : null}
                  {uploadBusy || analyzeBusy ? (
                    <ActivityIndicator color={palette.data} size="small" />
                  ) : null}
                </View>

                {upload.kind === 'ready' ? (
                  <View style={styles.uploadMeta}>
                    <Text selectable style={styles.metaText}>
                      {uploadMetaLabel(upload.upload)}
                    </Text>
                    <Text selectable style={styles.metaText}>
                      upload {shortId(upload.upload.id ?? '', 12)} ·{' '}
                      {upload.upload.mime ?? 'unknown mime'}
                    </Text>
                  </View>
                ) : upload.kind === 'uploading' ? (
                  <Text style={styles.composerHint}>
                    Uploading {upload.filename}…
                  </Text>
                ) : upload.kind === 'deleting' ? (
                  <Text style={styles.composerHint}>Removing image…</Text>
                ) : upload.kind === 'error' ? (
                  <View style={styles.publishStatus}>
                    <Text style={styles.publishFailure}>{upload.message}</Text>
                    <ErrorList errors={upload.errors} />
                  </View>
                ) : (
                  <Text style={styles.composerHint}>
                    {uploadEnabled
                      ? 'Pick a score photo, upload it, then Analyze.'
                      : 'Upload and Analyze are disabled until access is known.'}
                  </Text>
                )}

                <Text style={styles.composerHint}>
                  Draft review state starts at pending. Nothing is published from
                  this panel.
                </Text>
              </View>

              <View style={styles.card}>
                <Text style={[type.section, styles.cardLabel]}>
                  {catalog.source === 'api' ? 'API example' : 'Embedded template'}
                </Text>
                <Text style={styles.cardTitle}>{selection.title}</Text>
                {selection.id ? (
                  <Text selectable style={styles.templateId}>
                    id {selection.id}
                  </Text>
                ) : null}
                <Text style={styles.hint}>
                  Picking a pattern or meter loads a known-good example and replaces
                  the editor contents. The JSON below is always the source of truth
                  for a run.
                </Text>
                {catalog.loading ? (
                  <Text style={styles.catalogNote}>Loading examples…</Text>
                ) : catalog.note ? (
                  <Text style={styles.catalogWarning}>{catalog.note}</Text>
                ) : null}

                <Text style={styles.fieldLabel}>Pattern</Text>
                <View style={styles.chips}>
                  {patternChoices.map((pattern) => (
                    <Chip
                      key={pattern}
                      label={patternLabel(pattern)}
                      active={selection.pattern === pattern}
                      accessibilityLabel={patternLabel(pattern)}
                      onPress={() => choosePattern(pattern)}
                    />
                  ))}
                </View>
                <Text style={styles.composerHint}>{patternCatalogHint(samples)}</Text>

                <Text style={styles.fieldLabel}>Meter</Text>
                <View style={styles.chips}>
                  {meterChoices.map((meter) => (
                    <Chip
                      key={meter}
                      label={meterLabel(meter)}
                      active={selection.meter === meter}
                      accessibilityLabel={meterLabel(meter)}
                      onPress={() => chooseMeter(meter)}
                    />
                  ))}
                </View>

                <View style={styles.editorHeader}>
                  <View>
                    <Text style={[type.section, styles.cardLabel]}>Spec JSON</Text>
                    <Text style={styles.hint}>One sentence spec mapping.</Text>
                  </View>
                  <Text style={styles.stats}>
                    {stats.lines} lines · {stats.chars} chars
                  </Text>
                </View>

                <TextInput
                  multiline
                  value={specText}
                  onChangeText={(next) => {
                    setSpecText(next);
                    setDirty(true);
                  }}
                  style={styles.editor}
                  accessibilityLabel="Sentence spec JSON"
                  autoCapitalize="none"
                  autoCorrect={false}
                  autoComplete="off"
                  placeholder="Paste one sentence spec mapping…"
                  placeholderTextColor={palette.textFaint}
                  selectionColor={palette.data}
                  textAlignVertical="top"
                />

                <View style={styles.actions}>
                  <ActionButton
                    label="Validate"
                    onPress={() => void run('validate')}
                    disabled={running || publishing}
                    busy={result.kind === 'running' && result.action === 'validate'}
                  />
                  <ActionButton
                    label="Preview"
                    primary
                    onPress={() => void run('preview')}
                    disabled={running || publishing}
                    busy={result.kind === 'running' && result.action === 'preview'}
                  />
                  <ActionButton
                    label="Publish"
                    onPress={() => void publish()}
                    disabled={running || publishing}
                    busy={publishing}
                  />
                  {running || publishing ? (
                    <ActivityIndicator color={palette.data} size="small" />
                  ) : null}
                  {stale ? (
                    <Text style={styles.stale}>Edited since the last run.</Text>
                  ) : null}
                </View>

                <PublishStatus state={publishState} />
              </View>

              <View style={styles.card}>
                <Pressable
                  onPress={() => setShowFixture((open) => !open)}
                  accessibilityRole="button"
                  accessibilityState={{ expanded: showFixture }}
                  accessibilityLabel="Preview fixture"
                  style={({ pressed }) => [
                    styles.fixtureHeader,
                    pressed && styles.pressed,
                  ]}
                >
                  <View style={styles.fixtureHeaderText}>
                    <Text style={[type.section, styles.cardLabel]}>Preview fixture</Text>
                    <Text style={styles.cardTitle}>
                      {showFixture ? 'Fixture JSON' : 'Show the fixture sent with Preview'}
                    </Text>
                  </View>
                  <Text style={styles.fixtureToggle}>{showFixture ? '−' : '+'}</Text>
                </Pressable>
                <Text style={styles.hint}>
                  Figure sentences use <Text style={styles.code}>length</Text>,{' '}
                  <Text style={styles.code}>n</Text>,{' '}
                  <Text style={styles.code}>closes</Text>, and{' '}
                  <Text style={styles.code}>rise</Text>. Cell/cycle specs use{' '}
                  <Text style={styles.code}>run_length</Text>. API examples derive a
                  fixture from the spec; edit it for a different render.
                </Text>
                {showFixture ? (
                  <TextInput
                    multiline
                    value={fixtureJson}
                    onChangeText={(next) => {
                      setFixtureJson(next);
                      setDirty(true);
                    }}
                    style={[styles.editor, styles.fixtureEditor]}
                    accessibilityLabel="Preview fixture JSON"
                    autoCapitalize="none"
                    autoCorrect={false}
                    autoComplete="off"
                    placeholder="Preview fixture JSON…"
                    placeholderTextColor={palette.textFaint}
                    selectionColor={palette.data}
                    textAlignVertical="top"
                  />
                ) : null}
              </View>
            </View>

            <View style={[styles.column, wide && styles.columnWide]}>
              <View style={[styles.card, styles.resultCard]}>
                <View style={styles.resultHeader}>
                  <Text style={[type.section, styles.cardLabel]}>Gemini draft</Text>
                  <Text style={styles.actionLabel}>TextureSpec notes</Text>
                </View>

                {draftState.kind === 'idle' ? (
                  <>
                    <Text style={styles.cardTitle}>Nothing analyzed yet</Text>
                    <Text style={styles.hint}>
                      Upload a score image on the left, then Analyze. The draft is
                      read-only here: it is a TextureSpec note list, not one
                      SentenceSpec, so it must not be loaded into the editor
                      automatically.
                    </Text>
                  </>
                ) : draftState.kind === 'running' ? (
                  <View style={styles.loadingRow}>
                    <ActivityIndicator color={palette.data} />
                    <Text style={styles.loadingText}>
                      Reading the image with Gemini…
                    </Text>
                  </View>
                ) : draftState.kind === 'error' ? (
                  <>
                    <Text style={styles.failureTitle}>{draftState.message}</Text>
                    <ErrorList errors={draftState.errors} />
                    <Text style={styles.hint}>
                      Fix the upload or try again. The sentence editor is
                      unaffected.
                    </Text>
                  </>
                ) : (
                  <>
                    <View style={styles.badgeRow}>
                      <Badge
                        ok={draftState.draft.ok}
                        label={draftState.draft.ok ? 'DRAFT OK' : 'ANALYZE FAILED'}
                      />
                      {draftState.draft.cached ? <Badge ok label="CACHED" /> : null}
                      {draftState.draft.partial ? (
                        <Badge ok={false} label="PARTIAL" />
                      ) : null}
                    </View>
                    {draftState.draft.errors.length ? (
                      <ErrorList errors={draftState.draft.errors} />
                    ) : null}
                    {draftState.draft.partial ? (
                      <Text style={styles.catalogWarning}>
                        Partial draft: skipped{' '}
                        {draftState.draft.skippedChecks.length
                          ? draftState.draft.skippedChecks.join(', ')
                          : 'some checks'}{' '}
                        — no render context yet.
                      </Text>
                    ) : null}
                    {draftState.draft.warnings.length ? (
                      <View style={styles.warningList}>
                        <Text style={[type.section, styles.blockLabel]}>
                          Warnings
                        </Text>
                        {draftState.draft.warnings.map((warning, index) => (
                          <Text key={`warning:${index}`} style={styles.warningText}>
                            {warning}
                          </Text>
                        ))}
                      </View>
                    ) : null}

                    <ResultBlock
                      label="Measures"
                      lines={measureLines(draftState.draft.measures)}
                      empty="No measures returned."
                    />

                    <View style={styles.block}>
                      <View style={styles.blockHeader}>
                        <Text style={[type.section, styles.blockLabel]}>Notes</Text>
                        <Text style={styles.blockCount}>
                          {draftState.draft.notes.length}
                        </Text>
                      </View>
                      <DraftNotesTable notes={draftState.draft.notes} />
                    </View>

                    <View style={styles.actions}>
                      <ActionButton
                        label="Copy draft JSON"
                        onPress={() => void copyDraft()}
                      />
                      <ActionButton
                        label={showDraftJson ? 'Hide draft JSON' : 'Show draft JSON'}
                        onPress={() => setShowDraftJson((open) => !open)}
                      />
                    </View>
                    {copyNote ? (
                      <Text style={styles.composerHint}>{copyNote}</Text>
                    ) : null}
                    {showDraftJson ? (
                      <Text selectable style={styles.codeBlock}>
                        {valueLines(draftJson(draftState.draft), 120).join('\n')}
                      </Text>
                    ) : null}
                    <Text style={styles.composerHint}>
                      Draft state is pending review; copy the JSON into a
                      TextureSpec workflow when it is ready. The sentence editor
                      is untouched.
                    </Text>
                  </>
                )}
              </View>

              <ResultPanel
                result={result}
                stale={stale}
                audio={audio}
                audioSupported={Platform.OS === 'web'}
                canPlayAudio={previewSnapshot !== null}
                onPlayAudio={() => void playAudio()}
              />
              <PublishedPanel
                state={published}
                loadingId={loadingSpecId}
                rollback={rollbackState}
                confirmingId={confirmingRollbackId}
                onRefresh={() => void loadPublished()}
                onOpen={(id) => void openPublished(id)}
                onAskRollback={(id) => setConfirmingRollbackId(id)}
                onCancelRollback={() => setConfirmingRollbackId(null)}
                onConfirmRollback={(id) => void rollback(id)}
              />
              <View style={styles.endpoints}>
                <Text style={styles.endpointLabel}>Endpoints</Text>
                <Text selectable style={styles.endpoint}>
                  GET {studioAccessUrl()}
                </Text>
                <Text selectable style={styles.endpoint}>
                  POST {studioUploadsUrl()}
                </Text>
                <Text selectable style={styles.endpoint}>
                  POST {studioAnalyzeUrl()}
                </Text>
                <Text selectable style={styles.endpoint}>
                  GET {studioSentenceUrl('examples')}
                </Text>
                <Text selectable style={styles.endpoint}>
                  POST {studioSentenceUrl('validate')}
                </Text>
                <Text selectable style={styles.endpoint}>
                  POST {studioSentenceUrl('preview')}
                </Text>
                <Text selectable style={styles.endpoint}>
                  POST {studioSentenceUrl('audio')}
                </Text>
                <Text selectable style={styles.endpoint}>
                  POST {studioSentenceUrl('publish')}
                </Text>
                <Text selectable style={styles.endpoint}>
                  GET {studioSentenceUrl('specs')}
                </Text>
                <Text selectable style={styles.endpoint}>
                  POST {studioSentenceUrl('specs')}/{'<id>'}/rollback
                </Text>
              </View>
            </View>
          </View>
        </View>
      </ScrollView>
    </View>
  );
}

function Chip({
  label,
  active,
  onPress,
  accessibilityLabel,
}: {
  label: string;
  active: boolean;
  onPress: () => void;
  accessibilityLabel: string;
}) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      accessibilityState={{ selected: active }}
      style={({ pressed }) => [
        styles.chip,
        active && styles.chipActive,
        pressed && styles.pressed,
      ]}
    >
      <Text style={[styles.chipText, active && styles.chipTextActive]}>{label}</Text>
    </Pressable>
  );
}

function ActionButton({
  label,
  onPress,
  primary = false,
  disabled = false,
  busy = false,
}: {
  label: string;
  onPress: () => void;
  primary?: boolean;
  disabled?: boolean;
  busy?: boolean;
}) {
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled, busy }}
      style={({ pressed }) => [
        styles.button,
        primary ? styles.buttonPrimary : styles.buttonSecondary,
        pressed && !disabled ? styles.pressed : null,
        disabled ? styles.buttonDisabled : null,
      ]}
    >
      <Text style={[styles.buttonText, primary && styles.buttonTextPrimary]}>
        {label}
      </Text>
    </Pressable>
  );
}

function ErrorList({ errors }: { errors: StudioError[] }) {
  if (errors.length === 0) return null;
  return (
    <View style={styles.errorList}>
      {errors.map((error, index) => (
        <View key={`${error.path}:${index}`} style={styles.errorRow}>
          <Text selectable style={styles.errorPath}>
            {normalizeErrorPath(error.path)}
          </Text>
          <Text selectable style={styles.errorMessage}>
            {error.message}
          </Text>
        </View>
      ))}
    </View>
  );
}

function Badge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <View style={[styles.badge, ok ? styles.badgePass : styles.badgeFail]}>
      <Text style={[styles.badgeText, ok ? styles.badgeTextPass : styles.badgeTextFail]}>
        {label}
      </Text>
    </View>
  );
}

/** Compact draft table; confidence is coloured by band. */
function DraftNotesTable({ notes }: { notes: StudioAnalysisNote[] }) {
  const rows = draftNoteRows(notes);
  if (!notes.length) {
    return <Text style={styles.empty}>No notes in the draft.</Text>;
  }
  return (
    <View style={styles.table}>
      <View style={[styles.tableRow, styles.tableHead]}>
        <Text style={[styles.th, styles.colBar]}>Bar</Text>
        <Text style={[styles.th, styles.colBeat]}>Beat</Text>
        <Text style={[styles.th, styles.colVoice]}>Voice</Text>
        <Text style={[styles.th, styles.colPitch]}>Pitch</Text>
        <Text style={[styles.th, styles.colConf]}>Conf</Text>
        <Text style={[styles.th, styles.colConflict]}>Confl</Text>
      </View>
      {rows.map((row) => (
        <View key={`note:${row.index}`} style={styles.tableRow}>
          <Text style={[styles.td, styles.colBar]}>{row.bar}</Text>
          <Text style={[styles.td, styles.colBeat]}>{row.beat}</Text>
          <Text numberOfLines={1} style={[styles.td, styles.colVoice]}>
            {row.voice}
          </Text>
          <Text numberOfLines={1} style={[styles.td, styles.colPitch]}>
            {row.pitch}
            {row.position ? ` · ${row.position}` : ''}
          </Text>
          <Text
            style={[
              styles.td,
              styles.colConf,
              { color: CONFIDENCE_COLOR[row.band] },
            ]}
          >
            {row.confidence}
          </Text>
          <Text
            style={[
              styles.td,
              styles.colConflict,
              row.conflict ? styles.conflictCell : null,
            ]}
          >
            {row.conflict ? 'yes' : '—'}
          </Text>
        </View>
      ))}
      {notes.length > rows.length ? (
        <Text style={styles.composerHint}>
          … {notes.length - rows.length} more notes
        </Text>
      ) : null}
    </View>
  );
}

function ResultBlock({
  label,
  lines,
  empty,
}: {
  label: string;
  lines: string[];
  empty: string;
}) {
  return (
    <View style={styles.block}>
      <View style={styles.blockHeader}>
        <Text style={[type.section, styles.blockLabel]}>{label}</Text>
        {lines.length ? <Text style={styles.blockCount}>{lines.length}</Text> : null}
      </View>
      {lines.length ? (
        <Text selectable style={styles.codeBlock}>
          {lines.join('\n')}
        </Text>
      ) : (
        <Text style={styles.empty}>{empty}</Text>
      )}
    </View>
  );
}

function PublishStatus({ state }: { state: PublishState }) {
  if (state.kind === 'idle') return null;
  if (state.kind === 'running') {
    return (
      <View style={styles.publishStatus}>
        <ActivityIndicator color={palette.data} size="small" />
        <Text style={styles.publishStatusText}>Publishing current spec…</Text>
      </View>
    );
  }
  if (state.kind === 'failure') {
    return (
      <View style={styles.publishStatus}>
        <Text style={styles.publishFailure}>{state.message}</Text>
        <ErrorList errors={state.errors} />
      </View>
    );
  }
  return (
    <View style={styles.publishStatus}>
      <Text style={styles.publishOk}>
        Published v{state.version} · {shortId(state.id)}
      </Text>
      <Text style={styles.publishStatusText}>
        {patternLabel(state.pattern)} · {meterLabel(state.meter)}
      </Text>
    </View>
  );
}

function AudioControls({
  state,
  supported,
  canPlay,
  onPlay,
}: {
  state: AudioState;
  supported: boolean;
  canPlay: boolean;
  onPlay: () => void;
}) {
  if (!supported) {
    return (
      <View style={styles.audioRow}>
        <Text style={styles.audioText}>
          Audio playback is web-only in this sprint. The render hash and duration
          still identify the server-side WAV.
        </Text>
      </View>
    );
  }
  if (!canPlay) {
    return (
      <View style={styles.audioRow}>
        <Text style={styles.audioText}>
          Run a successful preview to render its short preview WAV.
        </Text>
      </View>
    );
  }
  return (
    <View style={styles.audioPanel}>
      <View style={styles.audioRow}>
        <ActionButton
          label={state.kind === 'loading' ? 'Rendering audio…' : 'Play preview'}
          onPress={onPlay}
          disabled={state.kind === 'loading'}
          busy={state.kind === 'loading'}
        />
        {state.kind === 'loading' ? (
          <Text style={styles.audioText}>Synthesizing the cached WAV…</Text>
        ) : state.kind === 'ready' ? (
          <Text style={styles.audioText}>
            {durationLabel(state.durationSec)} WAV
            {state.playing ? ' · playing' : ''}
          </Text>
        ) : state.kind === 'error' ? (
          <Text style={styles.audioText}>{state.message}</Text>
        ) : (
          <Text style={styles.audioText}>
            Calls /sentence/audio for this preview&apos;s spec and fixture.
          </Text>
        )}
      </View>
      {state.kind === 'error' ? <ErrorList errors={state.errors} /> : null}
    </View>
  );
}

function ResultPanel({
  result,
  stale,
  audio,
  audioSupported,
  canPlayAudio,
  onPlayAudio,
}: {
  result: StudioResult;
  stale: boolean;
  audio: AudioState;
  audioSupported: boolean;
  canPlayAudio: boolean;
  onPlayAudio: () => void;
}) {
  if (result.kind === 'idle') {
    return (
      <View style={[styles.card, styles.resultCard]}>
        <Text style={[type.section, styles.cardLabel]}>Result</Text>
        <Text style={styles.cardTitle}>Nothing run yet</Text>
        <Text style={styles.hint}>
          Validate checks the spec without rendering. Preview sends the spec plus a
          fixture and returns a plan, row, matrix, note list, and render hash.
        </Text>
        <View style={styles.emptyBox}>
          <Text style={styles.empty}>Validate or Preview to see output here.</Text>
        </View>
      </View>
    );
  }

  if (result.kind === 'running') {
    return (
      <View style={[styles.card, styles.resultCard]}>
        <Text style={[type.section, styles.cardLabel]}>Result</Text>
        <View style={styles.loadingRow}>
          <ActivityIndicator color={palette.data} />
          <Text style={styles.loadingText}>
            {result.action === 'validate' ? 'Validating spec…' : 'Rendering preview…'}
          </Text>
        </View>
      </View>
    );
  }

  if (result.kind === 'failure') {
    return (
      <View style={[styles.card, styles.resultCard]}>
        <View style={styles.resultHeader}>
          <Badge ok={false} label={result.sent ? 'REQUEST FAILED' : 'NOT SENT'} />
          <Text style={styles.actionLabel}>
            {result.action === 'validate' ? 'Validate' : 'Preview'}
          </Text>
        </View>
        <Text style={styles.failureTitle}>{result.message}</Text>
        <ErrorList errors={result.errors} />
        <Text style={styles.hint}>
          {result.sent
            ? 'The request was sent but the Studio API did not answer successfully. Check the backend and try again.'
            : 'The request was stopped in the app. Fix the highlighted JSON and run it again.'}
        </Text>
      </View>
    );
  }

  if (result.kind === 'validate') {
    const { data } = result;
    return (
      <View style={[styles.card, styles.resultCard]}>
        <View style={styles.resultHeader}>
          <Badge ok={data.ok} label={data.ok ? 'VALID' : 'INVALID'} />
          <Text style={styles.actionLabel}>Validate · {msLabel(result.elapsedMs)}</Text>
        </View>
        {stale ? <Text style={styles.stale}>Editor changed since this run.</Text> : null}
        <ErrorList errors={data.errors} />
        {data.ok && data.errors.length === 0 ? (
          <View style={styles.filledBox}>
            <Text style={styles.successText}>
              Spec accepted by the server. Run Preview to render a plan.
            </Text>
          </View>
        ) : !data.ok && data.errors.length === 0 ? (
          <View style={styles.filledBox}>
            <Text style={styles.empty}>
              Server rejected the spec without returning an error path.
            </Text>
          </View>
        ) : null}
      </View>
    );
  }

  const { data } = result;
  const plan = planLines(data.plan);
  const row = valueLines(data.row, 24);
  const matrix = valueLines(data.matrix, 40);
  const notes = notesLines(data.notes);
  const planEmpty =
    Array.isArray(data.plan) && data.plan.length === 0
      ? 'No spans matched this fixture. The select did not match, or the pattern/meter pair has no plan.'
      : 'No plan returned.';

  return (
    <View style={[styles.card, styles.resultCard]}>
      <View style={styles.resultHeader}>
        <Badge ok={data.ok} label={data.ok ? 'PREVIEW OK' : 'PREVIEW FAILED'} />
        <Text style={styles.actionLabel}>Preview · {msLabel(result.elapsedMs)}</Text>
      </View>
      {stale ? <Text style={styles.stale}>Editor changed since this run.</Text> : null}
      <ErrorList errors={data.errors} />

      <View style={styles.hashRow}>
        <Text style={[type.section, styles.blockLabel]}>Render hash</Text>
        <Text selectable style={styles.hash}>
          {data.renderHash ?? 'not returned'}
        </Text>
      </View>

      <AudioControls
        state={audio}
        supported={audioSupported}
        canPlay={canPlayAudio && data.ok}
        onPlay={onPlayAudio}
      />

      <ResultBlock label="Plan" lines={plan} empty={planEmpty} />
      <ResultBlock label="Row" lines={row} empty="No row returned." />
      <ResultBlock label="Matrix" lines={matrix} empty="No matrix returned." />
      <ResultBlock label="Notes" lines={notes} empty="No notes returned." />
    </View>
  );
}

function PublishedPanel({
  state,
  loadingId,
  rollback,
  confirmingId,
  onRefresh,
  onOpen,
  onAskRollback,
  onCancelRollback,
  onConfirmRollback,
}: {
  state: PublishedListState;
  loadingId: string | null;
  rollback: RollbackState;
  confirmingId: string | null;
  onRefresh: () => void;
  onOpen: (id: string) => void;
  onAskRollback: (id: string) => void;
  onCancelRollback: () => void;
  onConfirmRollback: (id: string) => void;
}) {
  return (
    <View style={styles.card}>
      <View style={styles.publishedHeader}>
        <View style={styles.fixtureHeaderText}>
          <Text style={[type.section, styles.cardLabel]}>Published specs</Text>
          <Text style={styles.cardTitle}>
            {state.items.length
              ? `${state.items.length} version${state.items.length === 1 ? '' : 's'}`
              : 'No versions yet'}
          </Text>
        </View>
        <Pressable
          onPress={onRefresh}
          disabled={state.loading}
          accessibilityRole="button"
          accessibilityLabel="Refresh published specs"
          style={({ pressed }) => [
            styles.refreshButton,
            pressed && styles.pressed,
            state.loading ? styles.buttonDisabled : null,
          ]}
        >
          <Text style={styles.refreshText}>{state.loading ? 'Loading…' : 'Refresh'}</Text>
        </Pressable>
      </View>

      {rollback.kind === 'ok' ? (
        <Text selectable style={styles.rollbackOk}>
          {rollbackLabel(rollback.version, rollback.rollbackOf) ?? 'Rollback complete.'}
        </Text>
      ) : null}
      {state.error ? <Text style={styles.catalogWarning}>{state.error}</Text> : null}
      {state.items.length === 0 && !state.loading && !state.error ? (
        <Text style={styles.empty}>
          Publish a spec to start its version history. Rows load the stored payload
          back into the editor.
        </Text>
      ) : null}

      {state.items.map((item) => {
        const lineage = publishedSpecLineage(item);
        return (
          <View key={item.id} style={styles.publishedRow}>
            <Pressable
              onPress={() => onOpen(item.id)}
              accessibilityRole="button"
              accessibilityLabel={`Load published ${publishedSpecTitle(item)}, ${publishedSpecMeta(item)}, id ${item.id}`}
              style={({ pressed }) => [
                styles.publishedOpen,
                pressed && styles.pressed,
              ]}
            >
              <View style={styles.publishedRowMain}>
                <Text style={styles.publishedTitle}>{publishedSpecTitle(item)}</Text>
                <Text selectable numberOfLines={1} style={styles.publishedId}>
                  {item.id}
                </Text>
                {lineage ? (
                  <Text selectable numberOfLines={1} style={styles.publishedLineage}>
                    {lineage}
                  </Text>
                ) : null}
              </View>
              <View style={styles.publishedRight}>
                <Text style={styles.publishedVersion}>v{item.version}</Text>
                <Text style={styles.publishedTime}>
                  {publishedAtLabel(item.createdAt)}
                </Text>
              </View>
              {loadingId === item.id ? (
                <ActivityIndicator color={palette.data} size="small" />
              ) : null}
            </Pressable>
            <RollbackControl
              item={item}
              confirming={confirmingId === item.id}
              busy={rollback.kind === 'running' && rollback.id === item.id}
              failure={
                rollback.kind === 'failure' && rollback.id === item.id
                  ? rollback.message
                  : null
              }
              disabled={rollback.kind === 'running'}
              onAsk={() => onAskRollback(item.id)}
              onCancel={onCancelRollback}
              onConfirm={() => onConfirmRollback(item.id)}
            />
          </View>
        );
      })}
    </View>
  );
}

function RollbackControl({
  item,
  confirming,
  busy,
  failure,
  disabled,
  onAsk,
  onCancel,
  onConfirm,
}: {
  item: StudioPublishedSpec;
  confirming: boolean;
  busy: boolean;
  failure: string | null;
  disabled: boolean;
  onAsk: () => void;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  if (busy) {
    return (
      <View style={styles.rollbackArea}>
        <ActivityIndicator color={palette.data} size="small" />
        <Text style={styles.rollbackHint}>Rolling back…</Text>
      </View>
    );
  }
  if (confirming) {
    return (
      <View style={styles.rollbackArea}>
        <Text style={styles.rollbackHint}>Roll back to v{item.version}?</Text>
        <Pressable
          onPress={onConfirm}
          accessibilityRole="button"
          accessibilityLabel={`Confirm rollback to version ${item.version}`}
          style={({ pressed }) => [
            styles.rollbackButton,
            styles.rollbackConfirm,
            pressed && styles.pressed,
          ]}
        >
          <Text style={[styles.rollbackText, styles.rollbackConfirmText]}>Confirm</Text>
        </Pressable>
        <Pressable
          onPress={onCancel}
          accessibilityRole="button"
          accessibilityLabel="Cancel rollback"
          style={({ pressed }) => [
            styles.rollbackButton,
            pressed && styles.pressed,
          ]}
        >
          <Text style={styles.rollbackText}>Cancel</Text>
        </Pressable>
      </View>
    );
  }
  return (
    <View style={styles.rollbackArea}>
      {failure ? <Text style={styles.rollbackFailure}>{failure}</Text> : null}
      <Pressable
        onPress={onAsk}
        disabled={disabled}
        accessibilityRole="button"
        accessibilityLabel={`Roll back to ${publishedSpecTitle(item)}, version ${item.version}`}
        style={({ pressed }) => [
          styles.rollbackButton,
          pressed && !disabled ? styles.pressed : null,
          disabled ? styles.buttonDisabled : null,
        ]}
      >
        <Text style={styles.rollbackText}>Rollback</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: palette.background,
  },
  scroll: {
    padding: 20,
    paddingBottom: 40,
  },
  shell: {
    width: '100%',
    maxWidth: 1280,
    alignSelf: 'center',
    gap: 16,
  },
  header: {
    gap: 6,
  },
  eyebrowRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  eyebrow: {
    color: palette.data,
  },
  devBadge: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 3,
    borderWidth: 1,
    borderColor: palette.playhead,
  },
  devBadgeText: {
    color: palette.playhead,
    fontFamily: type.mono.fontFamily,
    fontSize: 9,
    lineHeight: 12,
    fontWeight: '700',
    letterSpacing: 0.8,
  },
  title: {
    color: palette.text,
  },
  subtitle: {
    maxWidth: 760,
    color: palette.textMuted,
    fontFamily: type.sans.fontFamily,
    fontSize: 13,
    lineHeight: 19,
  },
  columns: {
    gap: 16,
  },
  columnsWide: {
    flexDirection: 'row',
    alignItems: 'flex-start',
  },
  column: {
    gap: 16,
  },
  columnWide: {
    flex: 1,
    minWidth: 0,
  },
  card: {
    backgroundColor: palette.panel,
    borderWidth: 1,
    borderColor: palette.hairline,
    borderRadius: 10,
    padding: 14,
    gap: 10,
  },
  resultCard: {
    minHeight: 260,
  },
  cardLabel: {
    color: palette.textFaint,
  },
  cardTitle: {
    color: palette.text,
    fontFamily: type.sans.fontFamily,
    fontSize: 15,
    lineHeight: 20,
    fontWeight: '600',
  },
  templateId: {
    color: palette.textFaint,
    fontFamily: type.mono.fontFamily,
    fontSize: 11,
    lineHeight: 16,
  },
  catalogNote: {
    color: palette.data,
    fontFamily: type.sans.fontFamily,
    fontSize: 11,
    lineHeight: 16,
  },
  catalogWarning: {
    color: palette.playhead,
    fontFamily: type.sans.fontFamily,
    fontSize: 11,
    lineHeight: 16,
  },
  hint: {
    color: palette.textMuted,
    fontFamily: type.sans.fontFamily,
    fontSize: 12,
    lineHeight: 17,
  },
  code: {
    color: palette.text,
    fontFamily: type.mono.fontFamily,
    fontSize: 11,
  },
  fieldLabel: {
    marginTop: 4,
    color: palette.textMuted,
    fontFamily: type.section.fontFamily,
    fontSize: 11,
    lineHeight: 14,
    fontWeight: '700',
    letterSpacing: 1.2,
    textTransform: 'uppercase',
  },
  chips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  chip: {
    minHeight: 34,
    justifyContent: 'center',
    paddingHorizontal: 12,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: palette.hairlineStrong,
    backgroundColor: palette.surface,
  },
  chipActive: {
    borderColor: palette.data,
    backgroundColor: palette.dataFill,
  },
  chipText: {
    color: palette.textMuted,
    fontFamily: type.sans.fontFamily,
    fontSize: 13,
    lineHeight: 16,
    fontWeight: '500',
  },
  chipTextActive: {
    color: palette.text,
  },
  composerHint: {
    color: palette.textFaint,
    fontFamily: type.sans.fontFamily,
    fontSize: 11,
    lineHeight: 16,
  },
  editorHeader: {
    marginTop: 6,
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: 12,
  },
  stats: {
    color: palette.textFaint,
    fontFamily: type.mono.fontFamily,
    fontSize: 11,
    lineHeight: 16,
    fontVariant: ['tabular-nums'],
  },
  editor: {
    minHeight: 360,
    padding: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: palette.hairlineStrong,
    backgroundColor: palette.background,
    color: palette.text,
    fontFamily: type.mono.fontFamily,
    fontSize: 12,
    lineHeight: 18,
  },
  fixtureEditor: {
    minHeight: 140,
  },
  actions: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 10,
  },
  button: {
    minHeight: TOUCH_TARGET,
    minWidth: 104,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 18,
    borderRadius: 8,
    borderWidth: 1,
  },
  buttonSecondary: {
    borderColor: palette.hairlineStrong,
    backgroundColor: palette.surface,
  },
  buttonPrimary: {
    borderColor: palette.data,
    backgroundColor: palette.data,
  },
  buttonDisabled: {
    opacity: 0.5,
  },
  buttonText: {
    color: palette.text,
    fontFamily: type.sans.fontFamily,
    fontSize: 14,
    lineHeight: 18,
    fontWeight: '600',
  },
  buttonTextPrimary: {
    color: palette.background,
  },
  pressed: {
    opacity: 0.8,
  },
  stale: {
    color: palette.playhead,
    fontFamily: type.sans.fontFamily,
    fontSize: 11,
    lineHeight: 16,
  },
  publishStatus: {
    gap: 6,
    padding: 10,
    borderRadius: 8,
    backgroundColor: palette.surface,
    borderWidth: 1,
    borderColor: palette.hairline,
  },
  publishStatusText: {
    color: palette.textMuted,
    fontFamily: type.sans.fontFamily,
    fontSize: 11,
    lineHeight: 16,
  },
  publishOk: {
    color: palette.data,
    fontFamily: type.mono.fontFamily,
    fontSize: 12,
    lineHeight: 17,
  },
  publishFailure: {
    color: palette.sound,
    fontFamily: type.sans.fontFamily,
    fontSize: 12,
    lineHeight: 17,
    fontWeight: '600',
  },
  fixtureHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
  },
  fixtureHeaderText: {
    flex: 1,
    gap: 4,
  },
  fixtureToggle: {
    color: palette.textMuted,
    fontFamily: type.mono.fontFamily,
    fontSize: 20,
    lineHeight: 24,
  },
  resultHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
    flexWrap: 'wrap',
  },
  badge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 4,
  },
  badgePass: {
    backgroundColor: palette.dataFill,
  },
  badgeFail: {
    backgroundColor: palette.soundSoft,
  },
  badgeText: {
    fontFamily: type.mono.fontFamily,
    fontSize: 11,
    lineHeight: 15,
    fontWeight: '700',
    letterSpacing: 1,
  },
  badgeTextPass: {
    color: palette.data,
  },
  badgeTextFail: {
    color: palette.sound,
  },
  actionLabel: {
    color: palette.textFaint,
    fontFamily: type.mono.fontFamily,
    fontSize: 11,
    lineHeight: 16,
  },
  failureTitle: {
    color: palette.sound,
    fontFamily: type.sans.fontFamily,
    fontSize: 14,
    lineHeight: 20,
    fontWeight: '600',
  },
  errorList: {
    gap: 8,
  },
  errorRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    padding: 8,
    borderRadius: 6,
    backgroundColor: palette.surface,
    borderLeftWidth: 2,
    borderLeftColor: palette.sound,
  },
  errorPath: {
    color: palette.playhead,
    fontFamily: type.mono.fontFamily,
    fontSize: 11,
    lineHeight: 16,
  },
  errorMessage: {
    flex: 1,
    minWidth: 160,
    color: palette.text,
    fontFamily: type.sans.fontFamily,
    fontSize: 12,
    lineHeight: 16,
  },
  filledBox: {
    padding: 12,
    borderRadius: 8,
    backgroundColor: palette.surface,
    borderWidth: 1,
    borderColor: palette.hairline,
  },
  emptyBox: {
    marginTop: 6,
    padding: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderStyle: 'dashed',
    borderColor: palette.hairlineStrong,
  },
  successText: {
    color: palette.data,
    fontFamily: type.sans.fontFamily,
    fontSize: 13,
    lineHeight: 18,
  },
  loadingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingVertical: 24,
  },
  loadingText: {
    color: palette.textMuted,
    fontFamily: type.sans.fontFamily,
    fontSize: 13,
  },
  hashRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    justifyContent: 'space-between',
    gap: 12,
    padding: 10,
    borderRadius: 8,
    backgroundColor: palette.surface,
    flexWrap: 'wrap',
  },
  hash: {
    flex: 1,
    minWidth: 160,
    color: palette.text,
    fontFamily: type.mono.fontFamily,
    fontSize: 12,
    lineHeight: 18,
  },
  audioPanel: {
    gap: 8,
    padding: 10,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: palette.hairline,
    backgroundColor: palette.surface,
  },
  audioRow: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 10,
  },
  audioText: {
    flex: 1,
    minWidth: 160,
    color: palette.textMuted,
    fontFamily: type.sans.fontFamily,
    fontSize: 11,
    lineHeight: 16,
  },
  publishedHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
  },
  refreshButton: {
    minHeight: 34,
    justifyContent: 'center',
    paddingHorizontal: 12,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: palette.hairlineStrong,
    backgroundColor: palette.surface,
  },
  refreshText: {
    color: palette.textMuted,
    fontFamily: type.sans.fontFamily,
    fontSize: 12,
    lineHeight: 16,
    fontWeight: '600',
  },
  publishedRow: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 10,
    padding: 10,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: palette.hairline,
    backgroundColor: palette.surface,
  },
  publishedOpen: {
    flex: 1,
    minWidth: 180,
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 10,
  },
  publishedRowMain: {
    flex: 1,
    minWidth: 150,
    gap: 2,
  },
  publishedTitle: {
    color: palette.text,
    fontFamily: type.sans.fontFamily,
    fontSize: 13,
    lineHeight: 18,
    fontWeight: '600',
  },
  publishedId: {
    color: palette.textFaint,
    fontFamily: type.mono.fontFamily,
    fontSize: 10,
    lineHeight: 14,
  },
  publishedLineage: {
    color: palette.data,
    fontFamily: type.mono.fontFamily,
    fontSize: 10,
    lineHeight: 14,
  },
  rollbackArea: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    justifyContent: 'flex-end',
    gap: 6,
  },
  rollbackButton: {
    minHeight: 34,
    justifyContent: 'center',
    paddingHorizontal: 12,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: palette.hairlineStrong,
    backgroundColor: palette.background,
  },
  rollbackConfirm: {
    borderColor: palette.data,
    backgroundColor: palette.dataFill,
  },
  rollbackText: {
    color: palette.textMuted,
    fontFamily: type.sans.fontFamily,
    fontSize: 12,
    lineHeight: 16,
    fontWeight: '600',
  },
  rollbackConfirmText: {
    color: palette.text,
  },
  rollbackHint: {
    color: palette.textMuted,
    fontFamily: type.sans.fontFamily,
    fontSize: 11,
    lineHeight: 16,
  },
  rollbackFailure: {
    color: palette.sound,
    fontFamily: type.sans.fontFamily,
    fontSize: 11,
    lineHeight: 16,
    maxWidth: 260,
  },
  rollbackOk: {
    color: palette.data,
    fontFamily: type.mono.fontFamily,
    fontSize: 12,
    lineHeight: 17,
  },
  publishedRight: {
    alignItems: 'flex-end',
    gap: 2,
  },
  publishedVersion: {
    color: palette.data,
    fontFamily: type.mono.fontFamily,
    fontSize: 11,
    lineHeight: 15,
    fontWeight: '700',
  },
  publishedTime: {
    color: palette.textFaint,
    fontFamily: type.mono.fontFamily,
    fontSize: 10,
    lineHeight: 14,
  },
  block: {
    borderTopWidth: 1,
    borderTopColor: palette.hairline,
    paddingTop: 10,
    gap: 6,
  },
  blockHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  blockLabel: {
    color: palette.textFaint,
  },
  blockCount: {
    color: palette.textFaint,
    fontFamily: type.mono.fontFamily,
    fontSize: 11,
    lineHeight: 16,
  },
  codeBlock: {
    color: palette.text,
    fontFamily: type.mono.fontFamily,
    fontSize: 11,
    lineHeight: 17,
    padding: 10,
    borderRadius: 6,
    backgroundColor: palette.background,
  },
  empty: {
    color: palette.textFaint,
    fontFamily: type.sans.fontFamily,
    fontSize: 12,
    lineHeight: 17,
  },
  sessionText: {
    flex: 1,
    minWidth: 0,
    color: palette.textFaint,
    fontFamily: type.mono.fontFamily,
    fontSize: 10,
    lineHeight: 15,
  },
  noticeBox: {
    gap: 4,
    padding: 10,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: palette.playhead,
    backgroundColor: palette.surface,
  },
  noticeTitle: {
    color: palette.playhead,
    fontFamily: type.sans.fontFamily,
    fontSize: 12,
    lineHeight: 17,
    fontWeight: '600',
  },
  noticeText: {
    color: palette.textMuted,
    fontFamily: type.sans.fontFamily,
    fontSize: 11,
    lineHeight: 16,
  },
  importRow: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 10,
    padding: 10,
    borderRadius: 8,
    borderWidth: 1,
    borderStyle: 'dashed',
    borderColor: palette.hairlineStrong,
    backgroundColor: palette.background,
  },
  fileName: {
    flex: 1,
    minWidth: 160,
    color: palette.textMuted,
    fontFamily: type.mono.fontFamily,
    fontSize: 11,
    lineHeight: 16,
  },
  imagePreview: {
    width: '100%',
    height: 180,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: palette.hairline,
    backgroundColor: palette.background,
  },
  cropStage: {
    width: '100%',
    height: 280,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: palette.hairline,
    backgroundColor: palette.background,
    overflow: 'hidden',
  },
  cropSurface: {
    position: 'absolute',
    overflow: 'hidden',
  },
  cropImage: {
    width: '100%',
    height: '100%',
  },
  cropShade: {
    position: 'absolute',
    backgroundColor: 'rgba(8, 9, 12, 0.58)',
  },
  cropSelection: {
    position: 'absolute',
    borderWidth: 2,
    borderColor: palette.data,
    backgroundColor: palette.dataFill,
  },
  cropHandle: {
    position: 'absolute',
    width: 10,
    height: 10,
    borderRadius: 2,
    borderWidth: 1,
    borderColor: palette.background,
    backgroundColor: palette.data,
  },
  cropHandleNw: {
    left: -6,
    top: -6,
  },
  cropHandleNe: {
    right: -6,
    top: -6,
  },
  cropHandleSw: {
    left: -6,
    bottom: -6,
  },
  cropHandleSe: {
    right: -6,
    bottom: -6,
  },
  cropToolbar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    flexWrap: 'wrap',
    gap: 10,
  },
  cropMeta: {
    color: palette.textMuted,
    fontFamily: type.mono.fontFamily,
    fontSize: 11,
    lineHeight: 16,
    fontVariant: ['tabular-nums'],
  },
  uploadMeta: {
    gap: 2,
    padding: 8,
    borderRadius: 6,
    backgroundColor: palette.background,
  },
  metaText: {
    color: palette.textMuted,
    fontFamily: type.mono.fontFamily,
    fontSize: 10,
    lineHeight: 15,
  },
  badgeRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    gap: 6,
  },
  warningList: {
    gap: 4,
    padding: 8,
    borderRadius: 6,
    borderLeftWidth: 2,
    borderLeftColor: palette.playhead,
    backgroundColor: palette.surface,
  },
  warningText: {
    color: palette.textMuted,
    fontFamily: type.sans.fontFamily,
    fontSize: 11,
    lineHeight: 16,
  },
  table: {
    borderWidth: 1,
    borderColor: palette.hairline,
    borderRadius: 6,
    overflow: 'hidden',
  },
  tableRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderTopWidth: 1,
    borderTopColor: palette.hairline,
  },
  tableHead: {
    borderTopWidth: 0,
    backgroundColor: palette.surface,
  },
  th: {
    color: palette.textFaint,
    fontFamily: type.mono.fontFamily,
    fontSize: 9,
    lineHeight: 13,
    fontWeight: '700',
    letterSpacing: 0.6,
    textTransform: 'uppercase',
  },
  td: {
    color: palette.text,
    fontFamily: type.mono.fontFamily,
    fontSize: 10,
    lineHeight: 15,
  },
  conflictCell: {
    color: palette.sound,
    fontWeight: '700',
  },
  colBar: {
    flex: 0.7,
  },
  colBeat: {
    flex: 0.7,
  },
  colVoice: {
    flex: 1,
  },
  colPitch: {
    flex: 1.8,
  },
  colConf: {
    flex: 0.8,
    textAlign: 'right',
  },
  colConflict: {
    flex: 0.8,
    textAlign: 'right',
  },
  endpoints: {
    gap: 4,
    paddingHorizontal: 2,
  },
  endpointLabel: {
    color: palette.textFaint,
    fontFamily: type.section.fontFamily,
    fontSize: 10,
    lineHeight: 14,
    fontWeight: '700',
    letterSpacing: 1,
    textTransform: 'uppercase',
  },
  endpoint: {
    color: palette.textFaint,
    fontFamily: type.mono.fontFamily,
    fontSize: 10,
    lineHeight: 15,
  },
});
