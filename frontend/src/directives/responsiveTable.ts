import type { Directive } from 'vue'

function syncLabels(table: HTMLTableElement) {
  const labels = Array.from(table.tHead?.rows[0]?.cells ?? [], cell => cell.textContent?.trim() ?? '')
  for (const body of Array.from(table.tBodies)) {
    for (const row of Array.from(body.rows)) {
      Array.from(row.cells).forEach((cell, index) => { cell.dataset.label = labels[index] ?? '' })
    }
  }
}

export const responsiveTable: Directive<HTMLTableElement> = {
  mounted: syncLabels,
  updated: syncLabels,
}
