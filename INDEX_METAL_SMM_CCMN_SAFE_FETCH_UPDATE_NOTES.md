# Index Metal SMM/CCMN Safe Fetch Update

Scope: Index Center / Daily Index Fetch only.

Changes:
- Metal index primary auto source changed to Shanghai Metals Market (SMM / 上海有色网).
- Metal index fallback auto source changed to Changjiang Nonferrous Metals Network (CCMN / 长江有色金属网).
- Sina Finance and Eastmoney are no longer used by the metal fetch path.
- Added index-specific page/keyword parsing and broad value-range validation to prevent false Success values such as wrong fields or shared defaults.
- FX (Bank of China USD/HKD/GBP), Freight manual + carry-forward, Index Snapshot, Sales/Operation/Project Detail/Lifecycle logic are unchanged.

Metal mapping:
- STAINLESS_STEEL_304: SMM 304 stainless steel page; fallback CCMN stainless steel page.
- CARBON_STEEL: SMM hot-rolled coil / carbon steel page; fallback CCMN metal information page.
- ZINC: SMM zinc spot page; fallback CCMN zinc page.
- ALUMINIUM: SMM aluminium spot page; fallback CCMN aluminium page.
