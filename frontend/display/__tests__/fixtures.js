/**
 * Test fixtures for display.js refactoring
 * Representative entity stores for snapshot testing
 */

const emptyStore = {
  entities: {},
  rootIds: [],
  meta: {}
};

const pokerLeagueStore = {
  entities: {
    'page-1': {
      id: 'page-1',
      parent: null,
      display: 'page',
      props: { title: 'Poker League' },
      _created_seq: 1,
      _removed: false
    },
    'section-1': {
      id: 'section-1',
      parent: 'page-1',
      display: 'section',
      props: { title: 'Players' },
      _created_seq: 2,
      _removed: false
    },
    'player-1': {
      id: 'player-1',
      parent: 'section-1',
      display: 'card',
      props: { name: 'Alice', chips: 1500, wins: 3 },
      _created_seq: 3,
      _removed: false
    },
    'player-2': {
      id: 'player-2',
      parent: 'section-1',
      display: 'card',
      props: { name: 'Bob', chips: 1200, wins: 2 },
      _created_seq: 4,
      _removed: false
    },
    'metrics-section': {
      id: 'metrics-section',
      parent: 'page-1',
      display: 'section',
      props: { title: 'Stats' },
      _created_seq: 5,
      _removed: false
    },
    'metric-1': {
      id: 'metric-1',
      parent: 'metrics-section',
      display: 'metric',
      props: { label: 'Total Pot', value: 2700 },
      _created_seq: 6,
      _removed: false
    },
    'checklist-1': {
      id: 'checklist-1',
      parent: 'page-1',
      display: 'checklist',
      props: { title: 'Tasks' },
      _created_seq: 7,
      _removed: false
    },
    'task-1': {
      id: 'task-1',
      parent: 'checklist-1',
      props: { task: 'Setup table', done: true },
      _created_seq: 8,
      _removed: false
    },
    'task-2': {
      id: 'task-2',
      parent: 'checklist-1',
      props: { task: 'Deal cards', done: false },
      _created_seq: 9,
      _removed: false
    }
  },
  rootIds: ['page-1'],
  meta: { title: 'Poker League' }
};

const simpleTextStore = {
  entities: {
    'page-1': {
      id: 'page-1',
      parent: null,
      display: 'page',
      props: { title: 'Notes' },
      _created_seq: 1,
      _removed: false
    },
    'heading-1': {
      id: 'heading-1',
      parent: 'page-1',
      display: 'section',
      props: { title: 'Introduction' },
      _created_seq: 2,
      _removed: false
    },
    'text-1': {
      id: 'text-1',
      parent: 'heading-1',
      display: 'text',
      props: { text: 'This is a simple note.' },
      _created_seq: 3,
      _removed: false
    }
  },
  rootIds: ['page-1'],
  meta: { title: 'Notes' }
};

const nestedStore = {
  entities: {
    'page-1': {
      id: 'page-1',
      parent: null,
      display: 'page',
      props: { title: 'Dashboard' },
      _created_seq: 1,
      _removed: false
    },
    'section-1': {
      id: 'section-1',
      parent: 'page-1',
      display: 'section',
      props: { title: 'Overview' },
      _created_seq: 2,
      _removed: false
    },
    'card-1': {
      id: 'card-1',
      parent: 'section-1',
      display: 'card',
      props: { title: 'Status', value: 'Active' },
      _created_seq: 3,
      _removed: false
    },
    'image-1': {
      id: 'image-1',
      parent: 'section-1',
      display: 'image',
      props: { src: 'https://example.com/chart.png', alt: 'Chart', caption: 'Monthly trends' },
      _created_seq: 4,
      _removed: false
    }
  },
  rootIds: ['page-1'],
  meta: { title: 'Dashboard' }
};

module.exports = {
  emptyStore,
  pokerLeagueStore,
  simpleTextStore,
  nestedStore
};
