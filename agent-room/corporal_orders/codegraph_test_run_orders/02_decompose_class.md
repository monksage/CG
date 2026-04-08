# Decompose Class Into Graph Nodes

## Role

You are decomposing a legacy class into graph nodes and loading them into a running CodeGraph service. This class has real method-to-method calls — unlike the previous flat decomposition, the resulting graph must have edges.

## Objective

Take the code in the "Code" section below. Decompose it into nodes and edges, load into CodeGraph, and verify that the Dunbar circle context endpoint works correctly with a connected graph.

## How to decompose

Work in two phases.

**Phase 1 — Plan.** Before making any API calls, produce a decomposition plan:
- List every method/function and classify it: contour (has decision points) or micro (no decisions).
- For each micro, identify its parent — the contour node it will be inlined into. If a micro is called by multiple contours, pick the primary caller; note the shared usage in spec_ticket.
- Map all call relationships: which node calls which. These become edges.
- Write the plan out as a list before proceeding.

**Phase 2 — Load.** Execute the plan via API calls:
- Create all nodes via `POST /node`.
- Create all edges via `POST /edge`.
- Verify the graph structure matches the plan.

## Node rules

- A node is the smallest unit of code containing at least one decision (if/try/loop with condition).
- No decision = micro. Inline micro into its parent contour node. Do not create standalone micro nodes with zero edges — lesson from previous run.
- Node names are verbs: `validate_jwt`, `parse_config`, `build_query`. What_do only.
- Each node stores clean code without imports. Imports go into the `imports` field.
- Fill `accepts` and `returns` as JSON describing the contract.
- Fill `spec_ticket` (10-15 lines) and `spec_summary` (full description).
- Set `tags` as relevant domain tags.
- For a class: the class itself is not a node. Its methods are. If the class has `__init__` that only assigns attributes — that's a micro, inline it into the methods that depend on those attributes. If `__init__` has decisions — it's a contour node.

## Context

CodeGraph API is running at `http://localhost:39051`. Note: there are already 24 nodes from a previous experiment. Do not delete them — just add new nodes alongside.

Endpoints:
```
POST /node              — create node
POST /edge              — add edge {source_id, target_id, edge_type}
GET  /node/{id}         — read node
GET  /graph             — all node ids + edges
GET  /context/{id}      — Dunbar circle context package
GET  /search?query=     — search by id and spec_ticket
```

## Constraints

- Do not invent code. Decompose what is given.
- Do not refactor or optimize. Preserve logic as-is, even if it's ugly.
- Do not create standalone micro nodes. Every micro must be inlined into a parent.
- Every contour node must have at least one edge (calls, uses, extends, or tests). If a contour has zero edges after decomposition — reconsider whether it should be merged with a neighbor.
- Use `NO_PROXY=localhost,127.0.0.1` when making HTTP requests.

## Verification

1. `GET /graph` — new nodes and edges are present. Edges exist (non-zero count for the new nodes).
2. Pick a leaf node (few outgoing edges). `GET /context/{id}` — depth 0 has full code + specs, depth 1 has spec_summary + contract of neighbors.
3. Pick the most connected node. `GET /context/{id}` — verify all three Dunbar levels appear: depth 0 (as_is), depth 1 (summary), depth 2 (ticket). If the graph is deep enough, depth 999 nodes should show id only.
4. Node count matches Phase 1 plan. Edge count matches Phase 1 plan.
5. No standalone micro nodes (kind=micro with zero edges).

## Report

Write report to `corporal_reports/codegraph_test_run_orders/02_decompose_class_report.md`. Include:
- The full Phase 1 decomposition plan (nodes, micros inlined where, edges).
- Graph structure after loading (node count, edge count, most connected node).
- Verification results with actual /context output for the two test nodes.

## Subagent guidance

Do this yourself. Phase 1 requires understanding the entire class at once.

## Code

```
from model.model_dclass import TabletCell, TabletDataByChan, Templates, Cts
from model.Models.ExModel import ExModeler
from model.Supply.utils import Statistic as stat
from model.Models.Linear import Linear
from model.Models.LMS import LMS, lmcoef
import numpy as np

def row_major_to_column_major(data, rows, cols):
    """
    Переводит данные из построчного порядка в постолбцовый.
    
    Параметры:
        data (list): Исходный список элементов в построчном порядке.
        rows (int): Количество строк в исходных данных.
        cols (int): Количество столбцов в исходных данных.
    
    Возвращает:
        list: Список элементов в постолбцовом порядке.
    """
    if len(data) != rows * cols:
        raise ValueError("Длина данных не соответствует указанным размерам матрицы")
    
    column_major = []
    for col in range(cols):
        for row in range(rows):
            index = row * cols + col
            column_major.append(data[index])
    return column_major

class SignalProcessor:
    # Константы как в оригинале
    FRWRD = 3
    BCK_CT = 3
    BACK_THRES_PERCENT_FORWARD = 0.05
    BACK_THRES_PERCENT_BACKWARD = 0.04
    DIBKTOL = 15
    DOT_WINDOW = 10
    SIGDOT_OFFSET = 8
    MAX_INDEX = 39

    def __init__(self, data: list[int], cycles: int):
        self.data = np.array(data)
        self.cycles = cycles
        self.signal_found = False
        self.dot = None
        self.forwards = []
        self.backwards = []
        self.fit = None

    def process(self) -> tuple[list[int], list[int]]:
        """Process the signal data and return (unfit, fit) data."""
        if len(self.data) == 0:
            return self._empty_result()
            
        self._preprocess()
        self._find_dot_forward()
        self._find_dot_reverse()
        
        if not self._determine_dot_position():
            return self._empty_result()
            
        self._remove_background()
        self._create_fit()
        return self.data.tolist(), self.fit.tolist()

    def _empty_result(self) -> tuple[list[int], list[int]]:
        return [0] * self.cycles, [0] * self.cycles

    def _preprocess(self):
        """Preprocess the raw data by removing linear baseline."""
        if len(self.data) < 6:
            return
            
        lin = Linear(
            x=stat.xl(cycles=self.cycles)[:6],
            y=self.data[:6]
        )
        self.data = self.data - stat.xl(self.cycles) * lin.coef.slope + abs(lin.coef.intercept)
        self.data -= min(self.data)

    def _determine_dot_position(self) -> bool:
        """Determine the final dot position based on forward and backward analysis."""
        if self.forwards:
            self.dot = int(np.median(self.forwards))
            if self.backwards and max(self.backwards) > self.dot:
                self.dot = (self.dot + max(self.backwards)) // 2
            self.signal_found = True
        elif self.backwards:
            self.dot = max(self.backwards)
            self.signal_found = True
            
        return self.signal_found

    def _find_dot_forward(self):
        """Find signal onset by analyzing data forward."""
        if len(self.data) < 5:
            return
            
        try:
            dif = stat.get_diff_max(stat.savgol(self.data, 19, 3))
            d_max = dif.dy[dif.dy_max + 1] if dif.dy_max + 1 < len(dif.dy) else 0
        except:
            return

        for j in range(5, min(self.MAX_INDEX - self.FRWRD, len(self.data) - self.FRWRD)):
            start_idx = max(0, j - self.BCK_CT)
            d_avg = stat.rolling(self.data[start_idx: j + 1])
            dI = self.data[j + 1] - self.data[j] if j + 1 < len(self.data) else 0
            
            if not self._is_valid_forward_point(dI, d_avg, d_max):
                continue
                
            if self._has_exponential_rise(j, direction=1):
                self.forwards.append(j - 1)
                self.signal_found = True

    def _find_dot_reverse(self):
        """Find signal onset by analyzing data backward."""
        if len(self.data) < 5:
            return
            
        try:
            dif = stat.get_diff_max(stat.savgol(self.data, 19, 3))
            start_idx = min(np.argmax(self.data) - 5, len(self.data) - 1)
            d_max = dif.dy[dif.dy_max + 1] if dif.dy_max + 1 < len(dif.dy) else 0
            end_ct = max(0, dif.dy_max - 4)
        except:
            return

        for j in range(start_idx, end_ct - 1, -1):
            if j - self.BCK_CT < 0:
                continue
                
            d_avg = stat.rolling(self.data[j - self.BCK_CT: j + 1][::-1])
            dI = self.data[j + 1] - self.data[j] if j + 1 < len(self.data) else 0
            
            if not self._is_valid_backward_point(dI, d_avg, d_max):
                continue
                
            if self._has_exponential_rise(j, direction=-1):
                self.backwards.append(j + 1)
                self.signal_found = True

    def _is_valid_forward_point(self, dI: float, d_avg: float, d_max: float) -> bool:
        """Check if a point meets forward search criteria."""
        return (
            dI >= d_avg + self.BACK_THRES_PERCENT_FORWARD * (d_max - d_avg) and
            d_avg >= 0 and
            dI >= self.DIBKTOL
        )

    def _is_valid_backward_point(self, dI: float, d_avg: float, d_max: float) -> bool:
        """Check if a point meets backward search criteria."""
        return (
            dI <= d_avg + self.BACK_THRES_PERCENT_BACKWARD * (d_max - d_avg) and
            d_avg <= 0 and
            dI <= self.DIBKTOL
        )

    def _has_exponential_rise(self, j: int, direction: int) -> bool:
        """Check if the signal shows exponential rise characteristics."""
        for m in range(self.FRWRD):
            idx = j + m * direction
            if idx - 1 < 0 or idx + 2 >= len(self.data):
                return False
                
            if direction > 0:  # forward case
                condition = (
                    self.data[idx] - self.data[idx - 1] < 
                    (self.data[idx - 1] - self.data[idx + 2]) or
                    self.data[idx + 1] - self.data[idx] < 
                    (self.data[idx] - self.data[idx - 1])
                )
            else:  # backward case
                condition = (
                    self.data[idx] - self.data[idx - 1] >= 
                    (self.data[idx - 1] - self.data[idx + 2]) or
                    self.data[idx + 1] - self.data[idx] >= 
                    (self.data[idx] - self.data[idx - 1])
                )
            if condition:
                return False
        return True

    def _remove_background(self):
        """Remove background signal before the dot position."""
        if self.dot is None or self.dot <= 0:
            return
            
        left = max(0, self.dot - self.DOT_WINDOW)
        if left >= self.dot:
            return
            
        try:
            lin = Linear(
                x=stat.xl(self.cycles)[left: self.dot],
                y=self.data[left: self.dot]
            ).create_linear_data(stat.xl(self.cycles))
            self.data -= lin
            self.data[:self.dot] = 0
        except:
            pass

    def _create_fit(self):
        """Create the fitted signal using LMS algorithm."""
        if self.dot is None or self.dot >= len(self.data):
            return
            
        sigdot = min(self.MAX_INDEX, self.dot + self.SIGDOT_OFFSET)
        if sigdot > len(self.data):
            sigdot = len(self.data)
            
        try:
            lms = LMS(
                y=self.data[:sigdot],
                x=stat.xl(self.cycles)[:sigdot],
                coefs=lmcoef(L=self.data[sigdot - 1], k=1, x0=self.dot + 2)
            )
            lmsdata = lms.from_x(stat.xl(self.cycles))
            self.fit = np.concatenate([lmsdata[:sigdot], self.data[sigdot:]])
        except:
            self.fit = self.data.copy()


class Calculator:
    def __init__(self, line: list[TabletCell], exe_model: ExModeler | None = None):
        if not line or not line[0].raw_measures:
            self.cycles = 0
        else:
            self.cycles = len(line[0].raw_measures[0].data)
        if exe_model is not None:
            self.line = self._process_exe_line(line, exe_model)
        else:
            self.line = self._process_line(line)
        self.row_line = self.line
        self.col_line = row_major_to_column_major(self.line, 8, 12)
        self.thresholds = exe_model.thresholds
        self.cts = self._calculate_cts()

    def _process_exe_line(self, line: list[TabletCell], exmodel: ExModeler) -> list[TabletCell]:
        """Processed ExModeler line filler."""
        if not line:
            return line
        if isinstance(exmodel.response, list):
            chanwells = exmodel.response
        else:
            chanwells = exmodel.response.response
        for cell_id, cell in enumerate(line):
            if not cell.raw_measures:
                continue

            for chandata in cell.raw_measures:
                if cell.category == 0:
                    unfit = fit = [0] * self.cycles
                else:
                    well = next((p for p in chanwells if p.channel == chandata.chan), None)
                    unfit = fit = well.data[cell_id].final_data

                cell.fit_measures.append(TabletDataByChan(
                    chan=chandata.chan,
                    data=fit
                ))
                cell.unfit_measures.append(TabletDataByChan(
                    chan=chandata.chan,
                    data=unfit
                ))

        return line

    def _process_line(self, line: list[TabletCell]) -> list[TabletCell]:
        """Process all cells in the line."""
        if not line:
            return line
            
        for cell_id, cell in enumerate(line):
            if not cell.raw_measures:
                continue
                
            for chandata in cell.raw_measures:
                if cell.category == 0:
                    unfit = fit = [0] * self.cycles
                else:
                    unfit, fit = self._process_channel(cell.category, chandata.data)
                
                cell.fit_measures.append(TabletDataByChan(
                    chan=chandata.chan,
                    data=fit
                ))
                cell.unfit_measures.append(TabletDataByChan(
                    chan=chandata.chan,
                    data=unfit
                ))
        return line

    def _process_channel(self, category: int, data: list[int]) -> tuple[list[int], list[int]]:
        """Process single channel data based on cell category."""
        if category == 0:
            return [0] * self.cycles, [0] * self.cycles
        return SignalProcessor(data, self.cycles).process()
    
    def _find_thresholds(self):
        chans = Templates().chans
        threses = Templates().chans
        for tube_id, tube_val in enumerate(self.line):
            for chandata_id, unfit_chandata in enumerate(tube_val.unfit_measures):
                fit_dot = SignalProcessor.BCK_CT
                for k in unfit_chandata.data:
                    if fit_dot == self.cycles:
                        fit_dot = None
                        chans[unfit_chandata.chan] = fit_dot
                        break
                    if k > 0:
                        chans[unfit_chandata.chan] = fit_dot
                        break
                    fit_dot+=1
            for raw in tube_val.raw_measures:
                fit_dot = chans[raw.chan]
                if fit_dot is None:
                    continue
                threses[raw.chan].append(
                    stat.standard_deviation(
                        raw.data[max(0,fit_dot-SignalProcessor.DOT_WINDOW): 
                                 min(self.cycles, fit_dot-SignalProcessor.BCK_CT)]
                                )
                            )
        for k in threses.keys():
            thres = np.median(threses[k])
            if np.isnan(thres):
                thres = 0
            threses[k] = thres
        return threses
    
    def _calculate_cts(self, is_fitted: bool = True, thresholds=None):
        """Вычисляет пороговые циклы (CT) для каждого канала.
        
        Args:
            is_fitted: Использовать fitted или unfit measures
            thresholds: Свои пороги (если None - используются дефолтные)
        
        Returns:
            Словарь с CT значениями для каждого канала
        """
        thresholds = thresholds or self.thresholds
        results = Templates().chans  # Основные результаты CT
        display_results = Templates().chans  # Результаты для отображения
        
        for tube in self.line:
            measures = tube.fit_measures if is_fitted else tube.unfit_measures
            
            for channel_data in measures:
                channel = channel_data.chan
                current_threshold = thresholds[channel]
                
                # Если порог 0 - пропускаем расчет
                if current_threshold == 0:
                    results[channel].append('-')
                    display_results[channel].append('-')
                    continue
                
                # Вычисляем точки пересечения
                ct, ct_display = self._find_ct_values(
                    data=channel_data.data, 
                    threshold=current_threshold
                )
                
                # Записываем результаты
                results[channel].append(ct)
                display_results[channel].append(ct_display)
        
        return    Cts(
            display_ct=display_results,
            value_ct=results,
                ),Cts(display_ct={
                    key: row_major_to_column_major(value, rows=8, cols=12) 
                    for key, value in display_results.items()},
                    value_ct={
                    key: row_major_to_column_major(value, rows=8, cols=12) 
                    for key, value in results.items()
                     })

    
    def _find_ct_values(self, data, threshold):
        """Вспомогательный метод для нахождения CT значений."""
        ct, ct_display = self.find_intersection_x(arr=data, thres=threshold)
        
        if ct is None:
            return '-', '-'
        
        # Корректировка индексации (0-based → 1-based)
        return ct + 1, ct_display + 1
    
    
    def find_intersection_x(self, arr, thres):
        """
        Находит X пересечения горизонтальной линии y_const с ломаной, заданной массивом Y.
        :param arr: Массив Y-значений (X = индекс элемента).
        :param y_const: Y-координата горизонтальной линии.
        :return: X-координата пересечения (дробная, округлённая до 2 знаков) или None, если нет пересечения.
        """
        y_const = thres
        for i in range(len(arr) - 1):
            y_a, y_b = arr[i], arr[i + 1]
            
            # Проверяем, что y_const между y_a и y_b
            if (y_a <= y_const <= y_b) or (y_a >= y_const >= y_b):
                # Линейная интерполяция: X = i + (y_const - y_a) / (y_b - y_a)
                x_intersect = i + (y_const - y_a) / (y_b - y_a)
                return round(x_intersect,3), round(x_intersect,1)
        return None, None  # Нет пересечения
                


```
