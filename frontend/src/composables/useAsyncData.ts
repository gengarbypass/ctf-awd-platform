import { ref, type Ref } from 'vue'

export function useAsyncData<T>(loader: () => Promise<T>, initial: T) {
  const data = ref(initial) as Ref<T>
  const loading = ref(false)
  const loaded = ref(false)
  const error = ref('')

  async function load() {
    loading.value = true
    error.value = ''
    try {
      data.value = await loader()
      loaded.value = true
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : '数据加载失败，请重试。'
    } finally {
      loading.value = false
    }
  }

  return { data, loading, loaded, error, load }
}
