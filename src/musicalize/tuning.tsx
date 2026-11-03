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
  normalizeParams,
  paramsEqual,
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
  /** The latest saved/selected params. The next Play uses these. */
  savedParams: SonifyParams;
  /** The values the room is actually playing and sharing. */
  heardParams: SonifyParams;
  /** Draft differs from the active profile's saved values. */
  dirty: boolean;
  /** Saved params differ from what is currently heard. */
  savedDirty: boolean;
  /** Bumped only when Play asks for the latest saved params. */
  playNonce: number;
  setParam: (key: string, value: number) => void;
  select: (id: string) => void;
  /** Start a new listen with the latest saved params. */
  requestPlay: () => void;
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
  const [savedParams, setSavedParams] = useState<SonifyParams>(() =>
    normalizeParams(boot.params),
  );
  const [heardParams, setHeardParams] = useState<SonifyParams>(() =>
    normalizeParams(boot.params),
  );
  const [open, setOpen] = useState(false);
  const [schemaEnabled, setSchemaEnabled] = useState(true);
  const [loaded, setLoaded] = useState(false);
  const [playNonce, setPlayNonce] = useState(0);

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
      setSavedParams(match ? match.params : normalizeParams(boot.params));
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
  const savedDirty = !paramsEqual(savedParams, heardParams);

  const setParam = useCallback((key: string, value: number) => {
    setParams((current) => normalizeParams({ ...current, [key]: value }));
  }, []);

  const select = useCallback(
    (id: string) => {
      const next = selectProfile(store, id);
      setStore(next);
      const chosen = next.profiles.find((item) => item.id === id);
      if (chosen) {
        setParams(chosen.params);
        setSavedParams(chosen.params);
      }
    },
    [store],
  );

  const requestPlay = useCallback(() => {
    setHeardParams(savedParams);
    setPlayNonce((nonce) => nonce + 1);
  }, [savedParams]);

  const revert = useCallback(() => {
    const next = profile.params;
    setParams(next);
    setSavedParams(next);
  }, [profile.params]);

  const saveChanges = useCallback(() => {
    if (profile.id === DEFAULT_PROFILE_ID) {
      // Default is immutable. Saving a change creates a named copy.
      const next = createProfile(store, 'Bản của tôi', params);
      setStore(next.store);
      setParams(next.profile.params);
      setSavedParams(next.profile.params);
      return;
    }
    const shaped = normalizeParams(params);
    setStore(updateProfileParams(store, profile.id, shaped));
    setParams(shaped);
    setSavedParams(shaped);
  }, [params, profile.id, store]);

  const addProfile = useCallback(
    (name?: string) => {
      const next = createProfile(store, name ?? 'Bản của tôi', params);
      setStore(next.store);
      setParams(next.profile.params);
      setSavedParams(next.profile.params);
    },
    [params, store],
  );

  const duplicate = useCallback(
    (id?: string) => {
      const next = duplicateProfile(store, id ?? profile.id);
      setStore(next.store);
      setParams(next.profile.params);
      setSavedParams(next.profile.params);
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
        setSavedParams(fallback.params);
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
        setSavedParams({ ...DEFAULT_PARAMS });
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
    setSavedParams(active.params);
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
      savedParams,
      heardParams,
      dirty,
      savedDirty,
      playNonce,
      setParam,
      select,
      requestPlay,
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
      dirty,
      duplicate,
      enabled,
      exportProfiles,
      heardParams,
      importProfiles,
      open,
      params,
      playNonce,
      profile,
      remove,
      rename,
      requestPlay,
      reset,
      revert,
      saveChanges,
      savedDirty,
      savedParams,
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
