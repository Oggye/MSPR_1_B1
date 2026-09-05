import './DataPagination.css';

const makePageRange = (current, total) => {
  if (total <= 7) {
    return Array.from({ length: total }, (_, index) => index + 1);
  }

  const pages = new Set([1, total, current - 1, current, current + 1]);

  return [...pages]
    .filter(page => page >= 1 && page <= total)
    .sort((a, b) => a - b);
};

export function SlicePagination({
  value,
  onChange,
  pageCount = 10,
  disabled = false,
}) {
  const pages = Array.from({ length: pageCount }, (_, index) => index + 1);

  return (
    <div className="ob-slice-pagination">
      <div className="ob-slice-pagination__header">
        <div>
          <strong>Tranche d'analyse {value}/{pageCount}</strong>
          <span>
            Chaque tranche représente environ {Math.round(100 / pageCount)} %
            des données de chaque pays.
          </span>
        </div>
        <div className="ob-slice-pagination__badge">
          ~{Math.round(100 / pageCount)} %
        </div>
      </div>

      <div className="ob-slice-pagination__buttons">
        <button
          type="button"
          onClick={() => onChange(Math.max(1, value - 1))}
          disabled={disabled || value <= 1}
        >
          Précédente
        </button>

        {pages.map(page => (
          <button
            type="button"
            key={page}
            className={page === value ? 'is-active' : ''}
            onClick={() => onChange(page)}
            disabled={disabled}
            aria-current={page === value ? 'page' : undefined}
          >
            {page}
          </button>
        ))}

        <button
          type="button"
          onClick={() => onChange(Math.min(pageCount, value + 1))}
          disabled={disabled || value >= pageCount}
        >
          Suivante
        </button>
      </div>
    </div>
  );
}

export function PagePagination({
  page,
  total,
  pageSize,
  onChange,
  disabled = false,
}) {
  const totalPages = Math.max(1, Math.ceil((total || 0) / pageSize));
  const visiblePages = makePageRange(page, totalPages);

  if (totalPages <= 1) {
    return null;
  }

  return (
    <div className="ob-page-pagination">
      <button
        type="button"
        onClick={() => onChange(Math.max(1, page - 1))}
        disabled={disabled || page <= 1}
      >
        Précédent
      </button>

      <div className="ob-page-pagination__pages">
        {visiblePages.map((visiblePage, index) => {
          const previous = visiblePages[index - 1];
          const showGap = previous && visiblePage - previous > 1;

          return (
            <span key={visiblePage} className="ob-page-pagination__entry">
              {showGap && <span className="ob-page-pagination__gap">…</span>}
              <button
                type="button"
                className={visiblePage === page ? 'is-active' : ''}
                onClick={() => onChange(visiblePage)}
                disabled={disabled}
                aria-current={visiblePage === page ? 'page' : undefined}
              >
                {visiblePage}
              </button>
            </span>
          );
        })}
      </div>

      <button
        type="button"
        onClick={() => onChange(Math.min(totalPages, page + 1))}
        disabled={disabled || page >= totalPages}
      >
        Suivant
      </button>

      <span className="ob-page-pagination__meta">
        Page {page}/{totalPages}
      </span>
    </div>
  );
}
