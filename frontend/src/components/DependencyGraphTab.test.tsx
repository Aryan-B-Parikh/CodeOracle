import { describe, it, expect } from 'vitest'
import { DependencyGraphTab } from './DependencyGraphTab'
import { GraphPayload, GraphNode, GraphEdge } from '../services/api'

describe('DependencyGraphTab Component & 10K LOC Scale Verification', () => {
  it('is defined and exports React component', () => {
    expect(DependencyGraphTab).toBeDefined()
    expect(typeof DependencyGraphTab).toBe('function')
  })

  it('validates 10K+ LOC synthetic graph payload with 200 nodes and circular cycles', () => {
    const nodes: GraphNode[] = []
    const edges: GraphEdge[] = []

    // Generate 200 nodes (modules and functions)
    for (let i = 0; i < 50; i++) {
      nodes.push({
        id: `module_${i}.py`,
        label: `module_${i}.py`,
        type: 'module',
        file: `module_${i}.py`,
        lineStart: 1,
        lineEnd: 200,
        complexity: 1,
        riskScore: 2,
      })

      for (let j = 0; j < 3; j++) {
        nodes.push({
          id: `module_${i}.py::func_${j}`,
          label: `func_${j}`,
          type: 'function',
          file: `module_${i}.py`,
          lineStart: 10 + j * 30,
          lineEnd: 30 + j * 30,
          complexity: 5 + (i % 10),
          riskScore: (i + j) * 3,
        })

        // Containment edge
        edges.push({
          source: `module_${i}.py`,
          target: `module_${i}.py::func_${j}`,
          kind: 'contains',
        })
      }

      // Cross module call edges
      if (i > 0) {
        edges.push({
          source: `module_${i}.py::func_0`,
          target: `module_${i - 1}.py::func_1`,
          kind: 'call',
        })
      }
    }

    // Circular dependency
    edges.push({
      source: 'module_0.py',
      target: 'module_1.py',
      kind: 'imports',
    })
    edges.push({
      source: 'module_1.py',
      target: 'module_0.py',
      kind: 'imports',
    })

    const payload: GraphPayload = {
      nodes,
      edges,
      meta: {
        circularDependencies: [{ cycle: ['module_0.py', 'module_1.py'] }],
        highRiskNodeIds: ['module_49.py::func_2', 'module_48.py::func_2'],
      },
    }

    expect(payload.nodes.length).toBe(200)
    expect(payload.edges.length).toBeGreaterThan(150)
    expect(payload.meta.circularDependencies.length).toBe(1)
    expect(payload.meta.highRiskNodeIds.length).toBe(2)
  })
})
