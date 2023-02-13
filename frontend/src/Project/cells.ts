/** Class to query and transform cell labels. */

type Cell = { value: number; cell: number; t: number; c: number };
type CellMatrix = (0 | 1)[][];
type Overlaps = { overlaps: number[][]; numCells: number[]; maxCell: number };

class Cells {
  cells: Cell[];

  constructor(cells: Cell[]) {
    this.cells = cells;
  }

  /** Converts the cell list to a jagged array where element i is an array of cell ids that encode value i + numCells
   * @param t Time to generate cell array for.
   * @param c Feature to generate cell array for.
   * @returns Jagged array where element i is an array of cell ids that encode value i + numCells at time t
   */
  getOverlaps(t: number, c: number): Overlaps {
    const atT = this.cells.filter((cell) => cell.t === t && cell.c === c);
    const maxCell = atT.reduce((max, cell) => Math.max(max, cell.cell), 0);
    const maxValue = atT.reduce((max, cell) => Math.max(max, cell.value), 0);
    const overlaps = atT.filter((cell) => cell.value > maxCell);
    const matrix: number[][] = Array.from({ length: maxValue - maxCell }, () => []);
    const numCells: number[] = new Array(maxValue - maxCell).fill(0);
    // For each cell involved in overlap, push cell to matrix and record number of cells involved
    for (const entry of overlaps) {
      const cell = entry.cell;
      const value = entry.value;
      matrix[value - maxCell - 1].push(cell);
      numCells[value - maxCell - 1]++;
    }
    // Handle edge case where there are no overlaps to prevent gpu kernel from crashing
    if (matrix.length === 0) {
      matrix.push([0]);
      numCells.push(0);
    }
    return { overlaps: matrix, numCells: numCells, maxCell: maxCell };
  }

  /** Converts the cell list to a sparse matrix where the (i, j)th element is 1 if value i encodes cell j at time t.
   * @param t Time to generate cell array for.
   * @returns Cell matrix where the (i, j)th element is 1 if value i encodes cell j at time t and 0 otherwise
   */
  getMatrix(t: number, c: number): CellMatrix {
    const atT = this.cells.filter((cell) => cell.t === t && cell.c === c);
    const maxCell = atT.reduce((max, cell) => Math.max(max, cell.cell), 0);
    const maxValue = atT.reduce((max, cell) => Math.max(max, cell.value), 0);
    const matrix: CellMatrix = new Array(maxValue + 1)
      .fill(0)
      .map(() => new Array(maxCell + 1).fill(0));
    for (const cell of atT) {
      matrix[cell.value][cell.cell] = 1;
    }
    return matrix;
  }

  /** Converts the cell list to a reduced-size sparse matrix where the (i, j)th element is 1 if value i encodes cell j at time t.
   * Reduced in this case means that the minimum cell and value counts will also be stored and any cells and values below
   * those counts will be cut off.
   * @param t Time to generate cell array for.
   * @returns Object with cell matrix and minCell and minValue where the (i - minValue, j - minCell)th element
   * is 1 if value i encodes cell j at time t and 0 otherwise
   */
  getReducedMatrix(t: number, c: number): Object {
    const atT = this.cells.filter((cell) => cell.t === t && cell.c === c);
    const maxCell = atT.reduce((max, cell) => Math.max(max, cell.cell), 0);
    const maxValue = atT.reduce((max, cell) => Math.max(max, cell.value), 0);
    let minCell = atT.reduce((min, cell) => Math.min(min, cell.cell), Infinity);
    let minValue = atT.reduce((min, cell) => Math.min(min, cell.value), Infinity);
    if (minCell === Infinity) {
      minCell = 0;
    }
    if (minValue === Infinity) {
      minValue = 0;
    }
    const matrix: CellMatrix = new Array(maxValue - minValue + 1)
      .fill(0)
      .map(() => new Array(maxCell - minCell + 1).fill(0));
    for (const cell of atT) {
      matrix[cell.value - minValue][cell.cell - minCell] = 1;
    }
    return { cellMatrix: matrix, minCell: minCell, minValue: minValue };
  }

  /** Returns the cells that are present in a frame at time t.
   * @param {number} t Time to get cells in.
   * @returns List of cell ids
   */
  getCellsListAtTime(t: number, c: number) {
    let cells = this.cells.filter((cell) => cell.t === t && cell.c === c).map((cell) => cell.cell);
    cells = [...new Set(cells)];
    cells.sort((a, b) => a - b);
    return cells;
  }

  /** Returns times the cell is present in.
   * @param {number} cell Cell to get times for.
   * @returns List of times the cell is present in.
   */
  getTimes(cell: number) {
    let t = this.cells.filter((c) => c.cell === cell).map((c) => c.t);
    t = [...new Set(t)];
    t.sort((a, b) => a - b);
    return t;
  }

  /** Returns the cells that a value encodes at time t.
   * @param {number} value Value in segmentation image
   * @param {number} t Time to get cells in.
   * @returns List of cells
   */
  getCellsForValue(value: number, t: number, c: number) {
    let cells = this.cells
      .filter((cell) => cell.t === t && cell.c === c && cell.value === value)
      .map((cell) => cell.cell);
    cells = [...new Set(cells)];
    cells.sort((a, b) => a - b);
    return cells;
  }

  getNewCell() {
    return this.cells.reduce((max, cell) => Math.max(max, cell.cell), 0) + 1;
  }
}

export default Cells;
