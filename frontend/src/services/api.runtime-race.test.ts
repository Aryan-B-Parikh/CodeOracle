import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  fetchEntityExplanation,
  fetchRepositoryGraph,
} from './api'

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

describe('latest-request-wins runtime guards', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('does not let a slow older entity explanation overwrite the newer selection', async () => {
    const oldRequest = deferred<Response>()
    const newRequest = deferred<Response>()
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockImplementationOnce(() => oldRequest.promise)
      .mockImplementationOnce(() => newRequest.promise)

    const oldCall = fetchEntityExplanation('repo', 'entity-a')
    const newCall = fetchEntityExplanation('repo', 'entity-b')

    newRequest.resolve(new Response(JSON.stringify({ data: { entity: { name: 'entity-b' } } }), { status: 200 }))
    await expect(newCall).resolves.toMatchObject({ data: { entity: { name: 'entity-b' } } })

    oldRequest.resolve(new Response(JSON.stringify({ data: { entity: { name: 'entity-a' } } }), { status: 200 }))
    await expect(oldCall).resolves.toMatchObject({ data: { entity: { name: 'entity-b' } } })
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('does not let a slow older graph request overwrite the newer repository', async () => {
    const oldRequest = deferred<Response>()
    const newRequest = deferred<Response>()
    vi.spyOn(globalThis, 'fetch')
      .mockImplementationOnce(() => oldRequest.promise)
      .mockImplementationOnce(() => newRequest.promise)

    const graphA = fetchRepositoryGraph('repo-a')
    const graphB = fetchRepositoryGraph('repo-b')

    const graphBPayload = {
      data: {
        nodes: [{ id: 'B', label: 'Repository B', type: 'function', complexity: 1 }],
        edges: [],
        meta: { circularDependencies: [], highRiskNodeIds: [] },
      },
    }

    newRequest.resolve(new Response(JSON.stringify(graphBPayload), { status: 200 }))
    await expect(graphB).resolves.toMatchObject(graphBPayload)

    oldRequest.resolve(new Response(JSON.stringify({
      data: {
        nodes: [{ id: 'A', label: 'Repository A', type: 'function', complexity: 1 }],
        edges: [],
        meta: { circularDependencies: [], highRiskNodeIds: [] },
      },
    }), { status: 200 }))

    await expect(graphA).resolves.toMatchObject(graphBPayload)
  })
})
