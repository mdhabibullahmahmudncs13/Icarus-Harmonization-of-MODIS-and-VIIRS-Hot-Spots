// @vitest-environment jsdom
import { act, createElement } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { useAppState } from '../src/state/useAppState';
import { DEFAULT_STATE, type AppState } from '../src/state/urlState';

declare global {
  // eslint-disable-next-line no-var
  var IS_REACT_ACT_ENVIRONMENT: boolean;
}

/** What the hook gives the test: the state, and the setters. */
interface Harness {
  state: AppState;
  setView: ReturnType<typeof useAppState>['setView'];
  setMode: ReturnType<typeof useAppState>['setMode'];
  setAoi: ReturnType<typeof useAppState>['setAoi'];
  setDate: ReturnType<typeof useAppState>['setDate'];
  setPolygon: ReturnType<typeof useAppState>['setPolygon'];
}

let root: Root;
let container: HTMLDivElement;
let harness: Harness;

function Probe() {
  harness = useAppState();
  return null;
}

/** Mount the hook, so its first render reads the hash as it is now. */
function mount(): void {
  act(() => {
    root.render(createElement(Probe));
  });
}

/** Wait for jsdom's asynchronous history navigation to land. */
function settle(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 20));
}

beforeEach(() => {
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  // A sentinel entry puts the history cursor at the end of the stack, so a
  // test's own push is the last entry: without it a back() in an earlier test
  // leaves the cursor in the middle, and the next push overwrites the forward
  // entry instead of growing the stack.
  window.history.pushState(null, '', '/');
  window.location.hash = '';
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
  mount();
});

afterEach(() => {
  act(() => {
    root.unmount();
  });
  container.remove();
});

describe('useAppState', () => {
  it('starts from the hash', () => {
    // The state is read once, on the first render, so the hash has to be in
    // place before the hook mounts.
    act(() => {
      root.unmount();
    });
    window.location.hash = '#map?mode=raw&aoi=IND-C';
    root = createRoot(container);
    mount();
    expect(harness.state).toMatchObject({ view: 'map', mode: 'raw', aoi: 'IND-C' });
  });

  it('keeps both changes when two setters fire in one tick', () => {
    // The regression this guards: each setter copied the state as it was when
    // the setter was built, so the second change dropped the first.
    act(() => {
      harness.setView('map');
      harness.setAoi('IND-C');
    });
    expect(harness.state).toMatchObject({ view: 'map', aoi: 'IND-C' });
  });

  it('keeps every change when three setters fire in one tick', () => {
    act(() => {
      harness.setView('calendar');
      harness.setMode('raw');
      harness.setDate('2019-03-01');
    });
    expect(harness.state).toMatchObject({
      view: 'calendar',
      mode: 'raw',
      date: '2019-03-01',
    });
  });

  it('leaves a history entry so the back button can undo a change', () => {
    const before = window.history.length;
    act(() => {
      harness.setView('map');
    });
    expect(window.history.length).toBe(before + 1);
    expect(window.location.hash).toContain('#map');
  });

  it('adds no history entry when the state does not change', () => {
    act(() => {
      harness.setView('overview');
    });
    const after = window.history.length;
    act(() => {
      harness.setView('overview');
    });
    expect(window.history.length).toBe(after);
  });

  it('goes back to the previous state', async () => {
    act(() => {
      harness.setView('map');
    });
    await act(async () => {
      window.history.back();
      await settle();
    });
    expect(harness.state.view).toBe('overview');
  });

  it('picks up a hash the user edited by hand', () => {
    act(() => {
      window.location.hash = '#anomalies?mode=raw&aoi=NPL&date=2019-03-01';
      window.dispatchEvent(new HashChangeEvent('hashchange'));
    });
    expect(harness.state).toMatchObject({
      view: 'anomalies',
      mode: 'raw',
      aoi: 'NPL',
      date: '2019-03-01',
    });
  });

  it('leaves a usable area behind when a drawn shape is cleared', () => {
    // The regression this guards: clearing the shape kept the `custom` label,
    // which is not a preset id — the API answered 422 for every request.
    const ring: [number, number][] = [
      [88.2, 23],
      [88.6, 23],
      [88.6, 23.3],
    ];
    act(() => {
      harness.setPolygon(ring);
    });
    expect(harness.state).toMatchObject({ aoi: 'custom', polygon: ring });

    act(() => {
      harness.setPolygon(null);
    });
    expect(harness.state.polygon).toBeNull();
    expect(harness.state.aoi).not.toBe('custom');
    expect(harness.state.aoi).toBe(DEFAULT_STATE.aoi);
  });
});
