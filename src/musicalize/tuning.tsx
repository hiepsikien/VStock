import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { fetchParamsSchema } from '../api/client';
import { readLink } from './link';
import {
  DEFAULT_PARAMS,
  DEFAULT_PROFILE_ID,
  activeProfile,
  createProfile,
  deleteProfile,
  duplicateProfile,
  initialProfileStore,
  normalizeProfileStore,
  normalizeParams,
  paramsEqual,
  paramsKey,
  parseProfileStore,
  renameProfile,
  resetProfile,
  selectProfile,
  serializeProfileStore,
  updateProfileParams,
  type ProfileStore,
  type SonifyParams,
  type SonifyProfile,
} from './params';
import { loadProfileStore, saveProfileStore } from './profileStorage';

type TuningValue = {
  /** Server kill switch plus the build-time flag. */
  enabled: boolean;
  open: boolean;
  setOpen: (open: boolean) => void;
  store: ProfileStore;
  profile: SonifyProfile;
  /** The slider values. Changing these does not render audio. */
  params: SonifyParams;
  /** The values the room is actually playing and sharing. */
  heardParams: SonifyParams;
  /** Draft differs from the active profile's saved values. */
  dirty: boolean;
  /** Draft differs from what is heard. */
  heardDirty: boolean;
  previewNonce: number;
  setParam: (key: string, value: number) => void;
  select: (id: string) => void;
  /** Commit the draft and ask the room to play it. */
  commit: (next?: SonifyParams, preview?: boolean) => void;
  revert: () => void;
  saveChanges: () => void;
  addProfile: (name?: string) => void;
  duplicate: (id?: string) => void;
  rename: (id: string, name: string) => void;
  remove: (id: string) => void;
  reset: (id: string) => void;
  importProfiles: (text: string) => boolean;
  exportProfiles: () => string;
};

const TuningContext = createContext<TuningValue | null>(null);

const envEnabled =
  typeof process === 'undefined' || process.env.EXPO_PUBLIC_SONIFY_PARAMS !== '0';

export function TuningProvider({ children }: { children: React.ReactNode }) {
  const [boot] = useState(() => readLink());
  const [store, setStore] = useState<ProfileStore>(() => initialProfileStore());
  const [params, setParams] = useState<SonifyParams>(() => normalizeParams(boot.params));
  const [heardParams, setHeardParams] = useState<SonifyParams>(() =>
    normalizeParams(boot.params),
  );
  const [open, setOpen] = useState(false);
  const [schemaEnabled, setSchemaEnabled] = useState(true);
  const [loaded, setLoaded] = useState(false);
  const [previewNonce, setPreviewNonce] = useState(0);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const saved = await loadProfileStore();
      if (cancelled) return;
      if (!saved) {
        setLoaded(true);
        return;
      }
      // The URL is the source of truth. A matching saved profile gives the
      // room a name; otherwise the link opens Default with an unsaved draft.
      const active = saved.profiles.find(
        (profile) => profile.id === saved.activeId && paramsEqual(profile.params, boot.params),
      );
      const match =
        active ?? saved.profiles.find((profile) => paramsEqual(profile.params, boot.params));
      setStore(match ? selectProfile(saved, match.id) : { ...saved, activeId: DEFAULT_PROFILE_ID });
      setParams(normalizeParams(boot.params));
      setHeardParams(normalizeParams(boot.params));
      setLoaded(true);
    })();
    return () => {
      cancelled = true;
    };
  }, [boot.params]);

  useEffect(() => {
    const controller = new AbortController();
    void (async () => {
      try {
        const schema = await fetchParamsSchema(controller.signal);
        if (!controller.signal.aborted) setSchemaEnabled(schema.enabled !== false);
      } catch {
        // Offline boot keeps the bundled schema; the server flag is the closer.
      }
    })();
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!loaded) return;
    void saveProfileStore(store);
  }, [loaded, store]);

  const enabled = envEnabled && schemaEnabled;
  useEffect(() => {
    if (!enabled && open) setOpen(false);
  }, [enabled, open]);

  const profile = activeProfile(store);
  const dirty = !paramsEqual(params, profile.params);
  const heardDirty = !paramsEqual(params, heardParams);

  const setParam = useCallback((key: string, value: number) => {
    setParams((current) => normalizeParams({ ...current, [key]: value }));
  }, []);

  const select = useCallback(
    (id: string) => {
      const next = selectProfile(store, id);
      setStore(next);
      const chosen = next.profiles.find((item) => item.id === id);
      if (chosen) setParams(chosen.params);
    },
    [store],
  );

  const commit = useCallback(
    (next?: SonifyParams, preview = true) => {
      const shaped = normalizeParams(next ?? params);
      setParams(shaped);
      setHeardParams(shaped);
      if (preview) setPreviewNonce((nonce) => nonce + 1);
    },
    [params],
  );

  const revert = useCallback(() => {
    const next = profile.params;
    setParams(next);
    setHeardParams(next);
    setPreviewNonce((nonce) => nonce + 1);
  }, [profile.params]);

  const saveChanges = useCallback(() => {
    if (profile.id === DEFAULT_PROFILE_ID) {
      // Default is immutable. Saving a change creates a named copy.
      const next = createProfile(store, 'Bản của tôi', params);
      setStore(next.store);
      setParams(next.profile.params);
      return;
    }
    const shaped = normalizeParams(params);
    setStore(updateProfileParams(store, profile.id, shaped));
    setParams(shaped);
  }, [params, profile.id, store]);

  const addProfile = useCallback(
    (name?: string) => {
      const next = createProfile(store, name ?? 'Bản của tôi', params);
      setStore(next.store);
      setParams(next.profile.params);
    },
    [params, store],
  );

  const duplicate = useCallback(
    (id?: string) => {
      const next = duplicateProfile(store, id ?? profile.id);
      setStore(next.store);
      setParams(next.profile.params);
    },
    [profile.id, store],
  );

  const rename = useCallback(
    (id: string, name: string) => {
      setStore(renameProfile(store, id, name));
    },
    [store],
  );

  const remove = useCallback(
    (id: string) => {
      if (id === DEFAULT_PROFILE_ID) return;
      const next = deleteProfile(store, id);
      setStore(next);
      if (store.activeId === id) {
        const fallback = activeProfile(next);
        setParams(fallback.params);
        setHeardParams(fallback.params);
      }
    },
    [store],
  );

  const reset = useCallback(
    (id: string) => {
      if (id === DEFAULT_PROFILE_ID) return;
      const next = resetProfile(store, id);
      setStore(next);
      if (store.activeId === id) {
        setParams({ ...DEFAULT_PARAMS });
        setHeardParams({ ...DEFAULT_PARAMS });
        setPreviewNonce((nonce) => nonce + 1);
      }
    },
    [store],
  );

  const importProfiles = useCallback((text: string) => {
    const parsed = parseProfileStore(text);
    if (!parsed) return false;
    setStore(parsed);
    const active = activeProfile(parsed);
    setParams(active.params);
    setHeardParams(active.params);
    return true;
  }, []);

  const exportProfiles = useCallback(() => serializeProfileStore(store), [store]);

  const value = useMemo<TuningValue>(
    () => ({
      enabled,
      open,
      setOpen,
      store,
      profile,
      params,
      heardParams,
      dirty,
      heardDirty,
      previewNonce,
      setParam,
      select,
      commit,
      revert,
      saveChanges,
      addProfile,
      duplicate,
      rename,
      remove,
      reset,
      importProfiles,
      exportProfiles,
    }),
    [
      addProfile,
      commit,
      dirty,
      duplicate,
      enabled,
      exportProfiles,
      heardDirty,
      heardParams,
      importProfiles,
      open,
      params,
      previewNonce,
      profile,
      remove,
      rename,
      reset,
      revert,
      saveChanges,
      select,
      setParam,
      store,
    ],
  );

  return <TuningContext.Provider value={value}>{children}</TuningContext.Provider>;
}

export function useTuning(): TuningValue {
  const value = useContext(TuningContext);
  if (!value) throw new Error('useTuning must be used inside TuningProvider');
  return value;
}

/** Canonical identity for React keys and effect dependencies. */
export function heardParamsKey(params: SonifyParams): string {
  return paramsKey(params);
}

/** Kept for callers that only need a stable object without the hook. */
export function normalizeStoredProfiles(raw: unknown): ProfileStore {
  return normalizeProfileStore(raw);
}
