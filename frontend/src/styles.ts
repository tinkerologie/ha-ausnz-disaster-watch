import { css } from "lit";

/**
 * Shared card styles. Only Home Assistant design tokens and theme variables: spacing
 * `--ha-space-*`, type `--ha-font-*`/`--ha-line-height-*`, shape `--ha-border-radius-*`,
 * semantic `--ha-color-*`, the theme palette (`--red-color`, …) for official scales, and
 * text/divider colours. Light and dark themes follow automatically.
 */
export const cardStyles = css`
  :host {
    display: block;
    height: 100%;
    font-family: var(--ha-font-family-body);
    color: var(--primary-text-color);
    -webkit-font-smoothing: var(--ha-font-smoothing);
  }
  :host([embedded]) {
    height: auto;
  }
  ha-card,
  section.embedded {
    container-type: inline-size;
  }
  ha-card {
    height: 100%;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  section.embedded {
    display: flex;
    flex-direction: column;
  }
  .header {
    display: flex;
    align-items: center;
    gap: var(--ha-space-2);
    min-height: var(--ha-space-12);
    padding: var(--ha-space-2) var(--ha-space-2) 0 var(--ha-space-4);
  }
  .header ha-icon {
    color: var(--secondary-text-color);
    flex: none;
  }
  .header .heading {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
  }
  .header .subtitle {
    color: var(--secondary-text-color);
    font-size: var(--ha-font-size-s);
    line-height: var(--ha-line-height-condensed);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .header .title {
    min-width: 0;
    margin: 0;
    font-family: var(--ha-font-family-heading);
    font-size: var(--ha-font-size-l);
    font-weight: var(--ha-font-weight-medium);
    line-height: var(--ha-line-height-condensed);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .header .count {
    color: var(--secondary-text-color);
    font-size: var(--ha-font-size-s);
    font-weight: var(--ha-font-weight-normal);
  }
  .header .actions {
    display: flex;
    align-items: center;
    flex: none;
    color: var(--secondary-text-color);
  }
  .content {
    display: flex;
    flex-direction: column;
    gap: var(--ha-space-3);
    padding: var(--ha-space-2) var(--ha-space-4) var(--ha-space-4);
    min-height: 0;
  }
  .secondary {
    color: var(--secondary-text-color);
    font-size: var(--ha-font-size-s);
    line-height: var(--ha-line-height-normal);
  }
  .list {
    display: flex;
    flex-direction: column;
    margin: 0 calc(-1 * var(--ha-space-4));
  }
  .list-title {
    margin: var(--ha-space-2) 0 0;
    color: var(--secondary-text-color);
    font-size: var(--ha-font-size-s);
    font-weight: var(--ha-font-weight-medium);
    letter-spacing: 0.02em;
  }
  .row {
    display: flex;
    align-items: center;
    min-width: 0;
  }
  .row ha-md-list-item {
    flex: 1;
    min-width: 0;
    --md-list-item-leading-space: var(--ha-space-4);
    --md-list-item-trailing-space: var(--ha-space-4);
    --md-list-item-top-space: var(--ha-space-2);
    --md-list-item-bottom-space: var(--ha-space-2);
    --md-list-item-label-text-size: var(--ha-font-size-m);
    --md-list-item-supporting-text-size: var(--ha-font-size-s);
    --md-list-item-trailing-supporting-text-size: var(--ha-font-size-s);
    --ha-md-list-item-gap: var(--ha-space-3);
  }
  .row .link {
    flex: none;
    margin-inline-end: var(--ha-space-2);
    color: var(--secondary-text-color);
  }
  .row .headline,
  .row .supporting {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    white-space: normal;
    overflow-wrap: anywhere;
  }
  .row .row-badge {
    display: flex;
    flex-wrap: wrap;
    gap: var(--ha-space-1);
    margin: var(--ha-space-1) 0;
  }
  .row .trailing {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: var(--ha-space-1);
    white-space: nowrap;
  }
  .bubble {
    --tone: var(--grey-color);
    flex: none;
    display: flex;
    align-items: center;
    justify-content: center;
    width: var(--ha-space-9);
    height: var(--ha-space-9);
    border-radius: var(--ha-border-radius-pill);
    background-color: color-mix(in srgb, var(--tone) 20%, transparent);
    color: var(--tone);
  }
  .bubble.large {
    width: var(--ha-space-12);
    height: var(--ha-space-12);
  }
  .badge {
    --tone: var(--grey-color);
    display: inline-flex;
    align-items: center;
    gap: var(--ha-space-1);
    max-width: 100%;
    padding: 0 var(--ha-space-2);
    min-height: var(--ha-space-6);
    border-radius: var(--ha-border-radius-pill);
    background-color: color-mix(in srgb, var(--tone) 18%, transparent);
    color: var(--primary-text-color);
    font-size: var(--ha-font-size-s);
    font-weight: var(--ha-font-weight-medium);
    line-height: var(--ha-line-height-condensed);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .badge ha-icon {
    color: var(--tone);
    --mdc-icon-size: var(--ha-space-4);
    flex: none;
  }
  .empty {
    display: flex;
    align-items: center;
    gap: var(--ha-space-3);
    padding: var(--ha-space-2) 0;
    color: var(--secondary-text-color);
    font-size: var(--ha-font-size-m);
  }
  .empty ha-icon {
    flex: none;
  }
  ha-chip-set {
    display: flex;
    flex-wrap: wrap;
    gap: var(--ha-space-2);
  }
  ha-alert {
    display: block;
  }
  .more {
    align-self: flex-start;
  }
  hr.divider {
    width: 100%;
    margin: 0;
    border: none;
    border-top: var(--ha-border-width-sm) solid var(--divider-color);
  }
  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }
  :where(button.plain) {
    all: unset;
    box-sizing: border-box;
    cursor: pointer;
    border-radius: var(--ha-border-radius-lg);
  }
  :focus-visible {
    outline: var(--ha-border-width-md) solid var(--ha-color-focus, var(--primary-color));
    outline-offset: var(--ha-border-width-md);
  }
  /* Narrow sections-view cells (3 of 12 columns). */
  @container (max-width: 240px) {
    .header > ha-icon {
      display: none;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    *,
    *::before,
    *::after {
      animation: none !important;
      transition: none !important;
    }
  }
`;
