export type CartItem = { sku: string; name: string; unitCents: number; qty: number };
export type CartState = { items: CartItem[]; coupon: string | null };
export type CartAction =
  | { type: "add"; item: { sku: string; name: string; unitCents: number }; qty?: number }
  | { type: "remove"; sku: string }
  | { type: "setQty"; sku: string; qty: number }
  | { type: "applyCoupon"; code: string }
  | { type: "clear" };
const CODES = ["SAVE10", "HALFOFF"];
export function cartReducer(state: CartState, action: CartAction): CartState {
  switch (action.type) {
    case "add": {
      const qty = action.qty ?? 1;
      if (!Number.isInteger(qty) || qty <= 0) return state;
      const i = state.items.findIndex(x => x.sku === action.item.sku);
      if (i < 0) return { ...state, items: [...state.items, { ...action.item, qty }] };
      return { ...state, items: state.items.map((x, j) => j === i ? { ...x, qty: x.qty + qty } : x) };
    }
    case "remove": {
      if (!state.items.some(x => x.sku === action.sku)) return state;
      return { ...state, items: state.items.filter(x => x.sku !== action.sku) };
    }
    case "setQty": {
      if (!state.items.some(x => x.sku === action.sku)) return state;
      if (action.qty <= 0) return { ...state, items: state.items.filter(x => x.sku !== action.sku) };
      return { ...state, items: state.items.map(x => x.sku === action.sku ? { ...x, qty: action.qty } : x) };
    }
    case "applyCoupon": {
      const c = action.code.toUpperCase();
      return CODES.includes(c) ? { ...state, coupon: c } : state;
    }
    case "clear": return { items: [], coupon: null };
  }
}
export function cartTotals(state: CartState) {
  const subtotalCents = state.items.reduce((s, x) => s + x.unitCents * x.qty, 0);
  const discountCents = state.coupon === "SAVE10" ? Math.floor(subtotalCents * 0.1) : state.coupon === "HALFOFF" ? Math.min(Math.floor(subtotalCents * 0.5), 2000) : 0;
  const taxCents = Math.round((subtotalCents - discountCents) * 0.08);
  return { subtotalCents, discountCents, taxCents, totalCents: subtotalCents - discountCents + taxCents };
}
