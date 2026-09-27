import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { StatusBar } from './StatusBar'
import { api } from '@/api/client'

vi.mock('@/api/client', () => ({
  api: {
    health: vi.fn().mockResolvedValue({
      status: 'ok',
      session_id: 'abc-123',
      fps: 12,
      camera: 'cam-1',
      model: 'yolo-world',
      input_size: 640,
      device: 'cpu',
    }),
  },
}))

describe('test_status_bar_polls_health', () => {
  it('polls health and renders its fields', async () => {
    render(<StatusBar sourceHealth={null} />)
    await waitFor(() => expect(api.health).toHaveBeenCalled())
    expect(await screen.findByText(/abc-123/)).toBeInTheDocument()
    expect(screen.getByText(/cam-1/)).toBeInTheDocument()
  })

  it('shows the latest source.health detail when given', async () => {
    render(<StatusBar sourceHealth={{ code: 'blur', detail: 'Image looks blurry' }} />)
    expect(await screen.findByText(/Image looks blurry/)).toBeInTheDocument()
  })
})
