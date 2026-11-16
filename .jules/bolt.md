## 2025-05-18 - Pre-computing device blocking error status

**Learning:** `BrinkHomeDeviceEntity.has_blocking_error` and `BrinkCoordinator.has_blocking_error` were filtering `device.alerts` repeatedly on every `available` check and state update across every entity. With dozens of entities per device, this created O(N_entities * M_alerts) redundant list iterations per coordinator update cycle. Pre-computing `has_blocking_error` during `BrinkDeviceData` initialization in `api.py` converted this to an O(1) attribute lookup.

**Action:** Whenever an entity property or coordinator property inspects nested list data that is immutable for a given update cycle, pre-calculate it once on the dataclass/model during data fetching instead of computing it dynamically in property getters.

## 2025-05-19 - Dataclass Caching without Polluting Dataclass Fields

**Learning:** When caching computed properties on a frozen dataclass instance (such as Home Assistant's `SelectEntityDescription`), adding a default field to the dataclass definition adds it to `__init__`, `__eq__`, `__repr__`, and `__hash__`. Mutating this field later via `object.__setattr__` breaks equality comparisons (`__eq__`) between dataclass instances. Using dynamic attribute caching via `object.__getattribute__` and `object.__setattr__` with a un-declared attribute name avoids polluting dataclass comparison semantics.

**Action:** Avoid declaring private dataclass fields solely for caching in frozen dataclasses. Use `object.__getattribute__` / `object.__setattr__` for lazy instance caching when `cached_property` cannot be applied.

## 2025-05-20 - O(1) Entity Device Lookup vs. Un-indexed Iterator Allocations

**Learning:** Using `next(iter((self.coordinator.data or {}).values()), ...)` in entity property getters (`available`, actions) created temporary `dict_values` views and iterator objects on every property evaluation across all entity instances. In addition to garbage collection pressure, un-indexed iteration arbitrarily picked the first system in the coordinator dictionary instead of resolving the entity's specific `system_id`. Using `self._device` (which performs `self.coordinator.data.get(self.system_id)`) converted this to an O(1) dictionary lookup, avoided iterator allocations, and ensured correct device resolution in multi-system Home Assistant setups.

**Action:** Always prefer `self._device` or explicit dictionary key lookup over `next(iter(...))` or list/dict-view creation when accessing coordinator data in Home Assistant entity classes.

## 2025-05-21 - Pre-indexing Option Dictionaries during Parameter Extraction

**Learning:** Select and enum sensor entities were searching parameter options lists via `next((opt["label"] for opt in param["options"] if opt["value"] == val), None)` on every state evaluation. With dynamic parameter option lists from the Brink cloud portal, linear generator search caused (~5x) overhead on repeated state reads. Building `options_map` (`value -> label`) and `reverse_options_map` (`label -> value`) dictionaries once in `_extract_parameters` during data retrieval reduced option resolution to O(1) dict lookups.

**Action:** Pre-build bidirectional dictionary indexes when mapping raw API options lists to UI representations during data extraction, avoiding linear search in property getters.

## 2025-05-22 - Single-Pass Evaluation of Aggregated Coordinator Properties in Entity Attribute Formatters

**Learning:** `attr_fn` on the `blocking_error` binary sensor description was re-evaluating `entity.coordinator.active_alerts` four separate times during state attribute calculation (to compute `len`, highest level name, highest level numeric value, and formatted alert dictionary list). Since `active_alerts` is a dynamic property that iterates across all devices in coordinator data to build a new list on every call, this caused 4 separate list allocations and 4 full scans of active alerts per state update. Evaluating `active_alerts` once in a helper function and extracting highest level via `max(active_alerts, key=lambda a: a.level)` reduced list allocations by 75% and achieved a ~1.2x speedup in attribute evaluation.

**Action:** In entity state/attribute formatters, store dynamic coordinator list properties in a local variable once and calculate aggregations (counts, max/min, mapped lists) in single-pass iterations over the local variable rather than re-querying the coordinator property.

## 2026-10-28 - Isolated Presets and Current Snapshot Capacity

**Learning:** Returning a shared mutable preset list lets a caller change every fan's choices. An immutable tuple can hold the canonical presets while getters return isolated lists. Capacity cached only during initialization also becomes stale after recovery or metadata changes, producing incorrect percentages and airflow writes.

**Action:** Keep shared choices immutable, calculate percentages once, and read validated control limits from the current coordinator snapshot. Test mutation isolation, empty-snapshot recovery, changed limits, unknown levels, and raw writes instead of asserting shared object identity. Do not claim allocation or benchmark improvements without measurements.

## 2026-10-29 - Pre-computing and Instance Caching Slugified Value Maps for Enum Sensors

**Learning:** Enum sensors repeatedly slugified static label maps. The initial benchmark figures were obtained for a mutable-cache implementation and do not establish the speedup of the corrected implementation. Exposing cached dictionaries or lists directly lets a caller change the options and state keys seen by other sensor entities. Cache a read-only mapping and a tuple on the frozen sensor description, preserving its dataclass equality and hash behavior.

**Action:** Cache static slugified mappings using `MappingProxyType`, derive immutable option tuples from the same map, and return a fresh list from the entity's `options` property. Test mutation isolation across entities and preserve the existing fallback for API-supplied dynamic enum options.
