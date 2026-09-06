import type { CommercialTerms as Terms } from "../../types/businessRules";

export function CommercialTerms({ terms }: { terms: Terms }) {
  const amount = (value: string | null) => value === null ? "Needs pricing" : `${value} ${terms.currency}`;
  return <div className="commercial-terms">
    <dl className="commercial-totals">
      <div><dt>Merchandise subtotal</dt><dd>{amount(terms.subtotal)}</dd></div>
      <div><dt>Discount</dt><dd>−{amount(terms.discount)}</dd></div>
      <div><dt>Freight</dt><dd>+{amount(terms.freight)}</dd></div>
      <div className="commercial-final"><dt>Final total</dt><dd>{amount(terms.total)}</dd></div>
    </dl>
    {terms.applied.length > 0 && <ul>{terms.applied.map((text) => <li key={text}>{text}</li>)}</ul>}
    {terms.blockers.map(text => <p className="error-message" key={text}>{text}</p>)}
    {terms.review_required && <p className="rule-review">Approval required before XML export.</p>}
  </div>;
}
