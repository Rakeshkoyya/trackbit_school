/** Indian-rupee formatting for fee amounts (values arrive as Decimal strings). */
export const money = (v: string | number) => "₹" + Number(v).toLocaleString("en-IN");
