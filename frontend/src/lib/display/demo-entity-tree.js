/**
 * demo-entity-tree.js - Comprehensive mock entity tree for pattern testing
 *
 * This file exports a demo entity tree that covers:
 * - All pattern types (page, section, card, metric, text, image, checklist, table, list)
 * - All display hints and variants
 * - Edge cases (empty props, long text, deep nesting, many children)
 * - Real-world scenarios (budget tracker, task list, dashboard)
 */

export function getDemoEntityTree() {
  return {
    entities: {
      // Root page
      'demo-page': {
        id: 'demo-page',
        display: 'page',
        props: { title: 'aide Pattern Library' },
        _created_seq: 1
      },

      // Intro text
      'intro-text': {
        id: 'intro-text',
        parent: 'demo-page',
        display: 'text',
        props: {
          text: 'This page demonstrates all supported pattern types and display variants. Use it to verify rendering behavior and as a visual reference.'
        },
        _created_seq: 2
      },

      // ═══════════════════════════════════════════════════════════
      // SECTION 1: Metrics & Dashboard Patterns
      // ═══════════════════════════════════════════════════════════
      'section-metrics': {
        id: 'section-metrics',
        parent: 'demo-page',
        display: 'section',
        props: { title: 'Metrics & Dashboard' },
        _created_seq: 3
      },

      'metric-budget': {
        id: 'metric-budget',
        parent: 'section-metrics',
        display: 'metric',
        props: { label: 'Budget', value: '$1,350' },
        _created_seq: 4
      },

      'metric-tasks': {
        id: 'metric-tasks',
        parent: 'section-metrics',
        display: 'metric',
        props: { label: 'Tasks', count: 42 },
        _created_seq: 5
      },

      'metric-completion': {
        id: 'metric-completion',
        parent: 'section-metrics',
        display: 'metric',
        props: { name: 'Completion', value: '87%' },
        _created_seq: 6
      },

      'metric-users': {
        id: 'metric-users',
        parent: 'section-metrics',
        display: 'metric',
        props: { label: 'Active Users', value: 1247 },
        _created_seq: 7
      },

      // ═══════════════════════════════════════════════════════════
      // SECTION 2: Text Patterns & Variants
      // ═══════════════════════════════════════════════════════════
      'section-text': {
        id: 'section-text',
        parent: 'demo-page',
        display: 'section',
        props: { title: 'Text Patterns' },
        _created_seq: 8
      },

      'text-basic': {
        id: 'text-basic',
        parent: 'section-text',
        display: 'text',
        props: { text: 'This is basic text using the "text" prop.' },
        _created_seq: 9
      },

      'text-content': {
        id: 'text-content',
        parent: 'section-text',
        display: 'text',
        props: { content: 'This text uses the "content" prop fallback.' },
        _created_seq: 10
      },

      'text-body': {
        id: 'text-body',
        parent: 'section-text',
        display: 'text',
        props: { body: 'This text uses the "body" prop fallback.' },
        _created_seq: 11
      },

      'text-long': {
        id: 'text-long',
        parent: 'section-text',
        display: 'text',
        props: {
          text: 'This is a very long text to test how the renderer handles lengthy content. Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.'
        },
        _created_seq: 12
      },

      // ═══════════════════════════════════════════════════════════
      // SECTION 3: Card Patterns
      // ═══════════════════════════════════════════════════════════
      'section-cards': {
        id: 'section-cards',
        parent: 'demo-page',
        display: 'section',
        props: { title: 'Card Patterns' },
        _created_seq: 13
      },

      'card-basic': {
        id: 'card-basic',
        parent: 'section-cards',
        display: 'card',
        props: {
          title: 'Basic Card',
          status: 'active',
          priority: 'high',
          assigned_to: 'Alice'
        },
        _created_seq: 14
      },

      'card-name-fallback': {
        id: 'card-name-fallback',
        parent: 'section-cards',
        display: 'card',
        props: {
          name: 'Card with Name',
          value: 100,
          category: 'test'
        },
        _created_seq: 15
      },

      'card-empty': {
        id: 'card-empty',
        parent: 'section-cards',
        display: 'card',
        props: {},
        _created_seq: 16
      },

      'card-nested': {
        id: 'card-nested',
        parent: 'section-cards',
        display: 'card',
        props: { title: 'Card with Children' },
        _created_seq: 17
      },

      'card-nested-text': {
        id: 'card-nested-text',
        parent: 'card-nested',
        display: 'text',
        props: { text: 'This text is nested inside a card.' },
        _created_seq: 18
      },

      'card-nested-metric': {
        id: 'card-nested-metric',
        parent: 'card-nested',
        display: 'metric',
        props: { label: 'Nested', value: '42' },
        _created_seq: 19
      },

      // ═══════════════════════════════════════════════════════════
      // SECTION 4: Checklist Patterns
      // ═══════════════════════════════════════════════════════════
      'section-checklists': {
        id: 'section-checklists',
        parent: 'demo-page',
        display: 'section',
        props: { title: 'Checklist Patterns' },
        _created_seq: 20
      },

      'checklist-tasks': {
        id: 'checklist-tasks',
        parent: 'section-checklists',
        display: 'checklist',
        props: { title: 'Project Tasks' },
        _created_seq: 21
      },

      'checklist-item-1': {
        id: 'checklist-item-1',
        parent: 'checklist-tasks',
        props: { task: 'Design mockups', done: true },
        _created_seq: 22
      },

      'checklist-item-2': {
        id: 'checklist-item-2',
        parent: 'checklist-tasks',
        props: { task: 'Implement frontend', done: true },
        _created_seq: 23
      },

      'checklist-item-3': {
        id: 'checklist-item-3',
        parent: 'checklist-tasks',
        props: { task: 'Write tests', done: false },
        _created_seq: 24
      },

      'checklist-item-4': {
        id: 'checklist-item-4',
        parent: 'checklist-tasks',
        props: { task: 'Deploy to production', done: false },
        _created_seq: 25
      },

      'checklist-checked': {
        id: 'checklist-checked',
        parent: 'section-checklists',
        display: 'checklist',
        props: { name: 'Shopping List (checked prop variant)' },
        _created_seq: 26
      },

      'checklist-checked-1': {
        id: 'checklist-checked-1',
        parent: 'checklist-checked',
        props: { label: 'Milk', checked: true },
        _created_seq: 27
      },

      'checklist-checked-2': {
        id: 'checklist-checked-2',
        parent: 'checklist-checked',
        props: { label: 'Eggs', checked: false },
        _created_seq: 28
      },

      'checklist-checked-3': {
        id: 'checklist-checked-3',
        parent: 'checklist-checked',
        props: { label: 'Bread', checked: true },
        _created_seq: 29
      },

      // ═══════════════════════════════════════════════════════════
      // SECTION 5: Table Patterns
      // ═══════════════════════════════════════════════════════════
      'section-tables': {
        id: 'section-tables',
        parent: 'demo-page',
        display: 'section',
        props: { title: 'Table Patterns' },
        _created_seq: 30
      },

      'table-users': {
        id: 'table-users',
        parent: 'section-tables',
        display: 'table',
        props: {},
        _created_seq: 31
      },

      'table-user-1': {
        id: 'table-user-1',
        parent: 'table-users',
        props: { name: 'Alice Smith', role: 'Engineer', status: 'Active', projects: 5 },
        _created_seq: 32
      },

      'table-user-2': {
        id: 'table-user-2',
        parent: 'table-users',
        props: { name: 'Bob Johnson', role: 'Designer', status: 'Active', projects: 3 },
        _created_seq: 33
      },

      'table-user-3': {
        id: 'table-user-3',
        parent: 'table-users',
        props: { name: 'Carol Davis', role: 'Manager', status: 'Away', projects: 8 },
        _created_seq: 34
      },

      'table-user-4': {
        id: 'table-user-4',
        parent: 'table-users',
        props: { name: 'David Wilson', role: 'Engineer', status: 'Active', projects: 4 },
        _created_seq: 35
      },

      'table-user-5': {
        id: 'table-user-5',
        parent: 'table-users',
        props: { name: 'Eve Brown', role: 'Designer', status: 'Active', projects: 6 },
        _created_seq: 36
      },

      'table-expenses': {
        id: 'table-expenses',
        parent: 'section-tables',
        display: 'table',
        props: {},
        _created_seq: 37
      },

      'expense-1': {
        id: 'expense-1',
        parent: 'table-expenses',
        props: { date: '2026-03-01', item_name: 'Office Supplies', amount: '$125.50', category: 'Operations' },
        _created_seq: 38
      },

      'expense-2': {
        id: 'expense-2',
        parent: 'table-expenses',
        props: { date: '2026-03-02', item_name: 'Software License', amount: '$299.00', category: 'Technology' },
        _created_seq: 39
      },

      'expense-3': {
        id: 'expense-3',
        parent: 'table-expenses',
        props: { date: '2026-03-03', item_name: 'Team Lunch', amount: '$87.25', category: 'Team' },
        _created_seq: 40
      },

      // ═══════════════════════════════════════════════════════════
      // SECTION 6: List Patterns
      // ═══════════════════════════════════════════════════════════
      'section-lists': {
        id: 'section-lists',
        parent: 'demo-page',
        display: 'section',
        props: { title: 'List Patterns' },
        _created_seq: 41
      },

      'list-projects': {
        id: 'list-projects',
        parent: 'section-lists',
        display: 'list',
        props: {},
        _created_seq: 42
      },

      'list-item-1': {
        id: 'list-item-1',
        parent: 'list-projects',
        props: { name: 'Website Redesign', status: 'In Progress' },
        _created_seq: 43
      },

      'list-item-2': {
        id: 'list-item-2',
        parent: 'list-projects',
        props: { name: 'Mobile App', status: 'Planning' },
        _created_seq: 44
      },

      'list-item-3': {
        id: 'list-item-3',
        parent: 'list-projects',
        props: { name: 'API v2', status: 'Completed' },
        _created_seq: 45
      },

      'list-title': {
        id: 'list-title',
        parent: 'section-lists',
        display: 'list',
        props: {},
        _created_seq: 46
      },

      'list-title-1': {
        id: 'list-title-1',
        parent: 'list-title',
        props: { title: 'First Item', priority: 'High' },
        _created_seq: 47
      },

      'list-title-2': {
        id: 'list-title-2',
        parent: 'list-title',
        props: { title: 'Second Item', priority: 'Medium' },
        _created_seq: 48
      },

      // ═══════════════════════════════════════════════════════════
      // SECTION 7: Image Patterns
      // ═══════════════════════════════════════════════════════════
      'section-images': {
        id: 'section-images',
        parent: 'demo-page',
        display: 'section',
        props: { title: 'Image Patterns' },
        _created_seq: 49
      },

      'image-basic': {
        id: 'image-basic',
        parent: 'section-images',
        display: 'image',
        props: {
          src: "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='600' height='300'%3E%3Crect fill='%237C8C6E' width='600' height='300'/%3E%3Ctext x='50%25' y='50%25' fill='white' font-family='sans-serif' font-size='24' text-anchor='middle' dy='.3em'%3EBasic Image%3C/text%3E%3C/svg%3E",
          alt: 'Placeholder image'
        },
        _created_seq: 50
      },

      'image-caption': {
        id: 'image-caption',
        parent: 'section-images',
        display: 'image',
        props: {
          src: "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='600' height='300'%3E%3Crect fill='%238FA07E' width='600' height='300'/%3E%3Ctext x='50%25' y='50%25' fill='white' font-family='sans-serif' font-size='24' text-anchor='middle' dy='.3em'%3EImage with Caption%3C/text%3E%3C/svg%3E",
          alt: 'Image with caption',
          caption: 'Figure 1: This image demonstrates the caption feature'
        },
        _created_seq: 51
      },

      'image-url-fallback': {
        id: 'image-url-fallback',
        parent: 'section-images',
        display: 'image',
        props: {
          url: "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='600' height='300'%3E%3Crect fill='%23A3B394' width='600' height='300'/%3E%3Ctext x='50%25' y='50%25' fill='white' font-family='sans-serif' font-size='24' text-anchor='middle' dy='.3em'%3EURL Prop Fallback%3C/text%3E%3C/svg%3E",
          alt: 'Using url prop instead of src'
        },
        _created_seq: 52
      },

      // ═══════════════════════════════════════════════════════════
      // SECTION 8: Edge Cases & Special Scenarios
      // ═══════════════════════════════════════════════════════════
      'section-edge-cases': {
        id: 'section-edge-cases',
        parent: 'demo-page',
        display: 'section',
        props: { title: 'Edge Cases' },
        _created_seq: 53
      },

      'edge-special-chars': {
        id: 'edge-special-chars',
        parent: 'section-edge-cases',
        display: 'text',
        props: { text: 'Special characters: <script>alert("XSS")</script> & <b>HTML</b> & "quotes" & \'apostrophes\'' },
        _created_seq: 54
      },

      'edge-deep-nesting': {
        id: 'edge-deep-nesting',
        parent: 'section-edge-cases',
        display: 'card',
        props: { title: 'Deep Nesting Test (Level 1)' },
        _created_seq: 55
      },

      'edge-level-2': {
        id: 'edge-level-2',
        parent: 'edge-deep-nesting',
        display: 'card',
        props: { title: 'Level 2' },
        _created_seq: 56
      },

      'edge-level-3': {
        id: 'edge-level-3',
        parent: 'edge-level-2',
        display: 'card',
        props: { title: 'Level 3' },
        _created_seq: 57
      },

      'edge-level-4': {
        id: 'edge-level-4',
        parent: 'edge-level-3',
        display: 'text',
        props: { text: 'This text is nested 4 levels deep!' },
        _created_seq: 58
      },

      'edge-many-children': {
        id: 'edge-many-children',
        parent: 'section-edge-cases',
        display: 'list',
        props: {},
        _created_seq: 59
      },

      'many-child-1': {
        id: 'many-child-1',
        parent: 'edge-many-children',
        props: { name: 'Item 1' },
        _created_seq: 60
      },

      'many-child-2': {
        id: 'many-child-2',
        parent: 'edge-many-children',
        props: { name: 'Item 2' },
        _created_seq: 61
      },

      'many-child-3': {
        id: 'many-child-3',
        parent: 'edge-many-children',
        props: { name: 'Item 3' },
        _created_seq: 62
      },

      'many-child-4': {
        id: 'many-child-4',
        parent: 'edge-many-children',
        props: { name: 'Item 4' },
        _created_seq: 63
      },

      'many-child-5': {
        id: 'many-child-5',
        parent: 'edge-many-children',
        props: { name: 'Item 5' },
        _created_seq: 64
      },

      'many-child-6': {
        id: 'many-child-6',
        parent: 'edge-many-children',
        props: { name: 'Item 6' },
        _created_seq: 65
      },

      'many-child-7': {
        id: 'many-child-7',
        parent: 'edge-many-children',
        props: { name: 'Item 7' },
        _created_seq: 66
      },

      'many-child-8': {
        id: 'many-child-8',
        parent: 'edge-many-children',
        props: { name: 'Item 8' },
        _created_seq: 67
      },

      // ═══════════════════════════════════════════════════════════
      // SECTION 9: Real-World Budget Tracker Scenario
      // ═══════════════════════════════════════════════════════════
      'section-budget': {
        id: 'section-budget',
        parent: 'demo-page',
        display: 'section',
        props: { title: 'Budget Tracker (Real-World Scenario)' },
        _created_seq: 68
      },

      'budget-summary-card': {
        id: 'budget-summary-card',
        parent: 'section-budget',
        display: 'card',
        props: {
          title: 'March 2026 Summary',
          total_income: '$5,200',
          total_expenses: '$3,850',
          net_savings: '$1,350'
        },
        _created_seq: 69
      },

      'budget-metrics-section': {
        id: 'budget-metrics-section',
        parent: 'section-budget',
        display: 'card',
        props: { title: 'Key Metrics' },
        _created_seq: 70
      },

      'budget-metric-1': {
        id: 'budget-metric-1',
        parent: 'budget-metrics-section',
        display: 'metric',
        props: { label: 'Housing', value: '$1,500' },
        _created_seq: 71
      },

      'budget-metric-2': {
        id: 'budget-metric-2',
        parent: 'budget-metrics-section',
        display: 'metric',
        props: { label: 'Food', value: '$650' },
        _created_seq: 72
      },

      'budget-metric-3': {
        id: 'budget-metric-3',
        parent: 'budget-metrics-section',
        display: 'metric',
        props: { label: 'Transportation', value: '$400' },
        _created_seq: 73
      },

      'budget-metric-4': {
        id: 'budget-metric-4',
        parent: 'budget-metrics-section',
        display: 'metric',
        props: { label: 'Utilities', value: '$200' },
        _created_seq: 74
      },

      // ═══════════════════════════════════════════════════════════
      // SECTION 10: Auto-Detection Tests (no explicit display hint)
      // ═══════════════════════════════════════════════════════════
      'section-auto-detect': {
        id: 'section-auto-detect',
        parent: 'demo-page',
        display: 'section',
        props: { title: 'Auto-Detection (No Display Hint)' },
        _created_seq: 75
      },

      'auto-detect-text': {
        id: 'auto-detect-text',
        parent: 'section-auto-detect',
        props: { text: 'This should auto-detect as text pattern' },
        _created_seq: 76
      },

      'auto-detect-metric': {
        id: 'auto-detect-metric',
        parent: 'section-auto-detect',
        props: { label: 'Auto Metric', value: 999 },
        _created_seq: 77
      },

      'auto-detect-image': {
        id: 'auto-detect-image',
        parent: 'section-auto-detect',
        props: { src: "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='400' height='200'%3E%3Crect fill='%23C2CCB8' width='400' height='200'/%3E%3Ctext x='50%25' y='50%25' fill='white' font-family='sans-serif' font-size='18' text-anchor='middle' dy='.3em'%3EAuto-Detected Image%3C/text%3E%3C/svg%3E" },
        _created_seq: 78
      },

      'auto-detect-checklist': {
        id: 'auto-detect-checklist',
        parent: 'section-auto-detect',
        props: {},
        _created_seq: 79
      },

      'auto-checklist-item': {
        id: 'auto-checklist-item',
        parent: 'auto-detect-checklist',
        props: { task: 'This parent should auto-detect as checklist', done: false },
        _created_seq: 80
      },

      'auto-detect-table': {
        id: 'auto-detect-table',
        parent: 'section-auto-detect',
        props: {},
        _created_seq: 81
      },

      'auto-table-row': {
        id: 'auto-table-row',
        parent: 'auto-detect-table',
        props: { column1: 'Value 1', column2: 'Value 2' },
        _created_seq: 82
      }
    },
    rootIds: ['demo-page'],
    meta: {}
  };
}
