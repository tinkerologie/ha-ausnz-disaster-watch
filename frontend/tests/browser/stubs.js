/**
 * Test-only stand-ins for the Home Assistant elements the cards use, plus helpers to
 * build a `hass` object from the fixture and mount a card in a sections-style grid.
 * Never shipped: the real elements come from Home Assistant.
 */
const css = (text) => {
  const sheet = new CSSStyleSheet();
  sheet.replaceSync(text);
  return sheet;
};

class Base extends HTMLElement {
  constructor(styles = "") {
    super();
    this.attachShadow({ mode: "open" }).adoptedStyleSheets = [css(styles)];
  }
}

customElements.define(
  "ha-card",
  class extends Base {
    constructor() {
      super(`:host{display:block;background:var(--ha-card-background);border-radius:12px;border:1px solid var(--divider-color);color:var(--primary-text-color)}`);
      this.shadowRoot.innerHTML = "<slot></slot>";
    }
  },
);

customElements.define(
  "ha-icon",
  class extends Base {
    constructor() {
      super(`:host{display:inline-flex;width:var(--mdc-icon-size,24px);height:var(--mdc-icon-size,24px);border-radius:50%;background:currentColor;opacity:.55;flex:none}`);
    }
  },
);

class StubButton extends Base {
  constructor(styles = "") {
    super(`button,a{all:unset;cursor:pointer;display:inline-flex;align-items:center;gap:6px}button:focus-visible,a:focus-visible{outline:2px solid var(--primary-color)}${styles}`);
  }
}

customElements.define(
  "ha-icon-button",
  class extends StubButton {
    constructor() {
      super(`:host{display:inline-flex;width:40px;height:40px;align-items:center;justify-content:center}`);
    }
    connectedCallback() {
      const label = this.label ?? "";
      this.shadowRoot.innerHTML = this.href
        ? `<a part="link" href="${this.href}" target="${this.getAttribute("target") ?? ""}" rel="${this.getAttribute("rel") ?? ""}" aria-label="${label}"><slot></slot></a>`
        : `<button part="button" aria-label="${label}"><slot></slot></button>`;
    }
  },
);

customElements.define(
  "ha-button",
  class extends StubButton {
    constructor() {
      super(`button{color:var(--primary-color);font-weight:500;padding:6px 8px}`);
      this.shadowRoot.innerHTML = "<button><slot></slot></button>";
    }
  },
);

customElements.define(
  "ha-alert",
  class extends Base {
    constructor() {
      super(`:host{display:block;padding:8px 12px;border-radius:4px;background:var(--ha-color-fill-neutral-quiet-resting)}`);
      this.shadowRoot.innerHTML = `<div role="alert"><slot></slot></div>`;
    }
  },
);

customElements.define(
  "ha-chip-set",
  class extends Base {
    constructor() {
      super(`:host{display:flex;flex-wrap:wrap;gap:8px}`);
      this.setAttribute("role", "toolbar");
      this.shadowRoot.innerHTML = "<slot></slot>";
    }
  },
);

class StubChip extends StubButton {
  constructor() {
    super(`button{height:32px;padding:0 12px;border:1px solid var(--divider-color);border-radius:8px;font-size:14px;color:var(--primary-text-color)}
      :host([selected]) button{background:var(--ha-color-fill-neutral-normal-resting)} ::slotted(ha-icon){--mdc-icon-size:18px}`);
  }
  connectedCallback() {
    this.render();
  }
  set label(value) {
    this._label = value;
    this.render();
  }
  get label() {
    return this._label;
  }
  set selected(value) {
    this._selected = !!value;
    this.toggleAttribute("selected", !!value);
    this.render();
  }
  get selected() {
    return !!this._selected;
  }
  render() {
    const pressed = this.localName === "ha-filter-chip" ? ` aria-pressed="${this.selected}"` : "";
    this.shadowRoot.innerHTML = `<button${pressed}><slot name="icon"></slot><span>${this._label ?? ""}</span></button>`;
  }
}
customElements.define("ha-assist-chip", class extends StubChip {});
customElements.define("ha-filter-chip", class extends StubChip {});

customElements.define(
  "ha-md-list-item",
  class extends Base {
    constructor() {
      super(`:host{display:block}.item{all:unset;box-sizing:border-box;display:flex;align-items:center;gap:var(--ha-md-list-item-gap,16px);width:100%;padding:8px 16px;cursor:default}
        button.item{cursor:pointer}.text{flex:1;min-width:0;display:flex;flex-direction:column;font-size:14px}
        ::slotted([slot=supporting-text]){color:var(--secondary-text-color);font-size:12px}::slotted([slot=end]){font-size:12px;color:var(--secondary-text-color)}`);
    }
    connectedCallback() {
      const tag = this.getAttribute("type") === "button" ? "button" : "div";
      this.shadowRoot.innerHTML = `<${tag} class="item"><slot name="start"></slot><span class="text"><slot name="headline"></slot><slot name="supporting-text"></slot></span><slot name="end"></slot></${tag}>`;
    }
  },
);

customElements.define("ha-tooltip", class extends Base {});

/** Build a hass object from the fixture with HA-like formatters. */
window.makeHass = (fixture, { darkMode = false, states = {} } = {}) => {
  const allStates = { ...structuredClone(fixture.states), ...states };
  const number = (v) => new Intl.NumberFormat("en").format(v);
  return {
    states: allStates,
    entities: fixture.entities,
    devices: fixture.devices,
    locale: { language: "en", time_zone: "server" },
    language: "en",
    config: fixture.config,
    themes: { darkMode },
    connection: {
      messages: [],
      async sendMessagePromise(message) {
        this.messages.push(message);
        if (message.type === "map_tiles/access_token") return { token: "test-token" };
        if (message.type === "auth/sign_path") return { path: `${message.path}?authSig=test` };
        return {};
      },
      addEventListener() {},
      removeEventListener() {},
    },
    formatEntityState(stateObj) {
      const value = Number(stateObj.state);
      const unit = stateObj.attributes.unit_of_measurement;
      const shown = stateObj.state !== "" && Number.isFinite(value) ? number(value) : stateObj.state;
      return unit ? `${shown} ${unit}` : shown;
    },
    formatEntityAttributeValue(_stateObj, _attribute, value) {
      return typeof value === "number" ? number(value) : String(value ?? "");
    },
  };
};

/** Mount a card as the sections view does: setConfig, hass, grid size from getGridOptions. */
window.mountCard = async (tag, config, hass) => {
  await customElements.whenDefined(tag);
  const grid = document.getElementById("grid");
  const el = document.createElement(tag);
  el.setConfig({ type: `custom:${tag}`, ...config });
  el.hass = hass;
  const options = el.getGridOptions?.() ?? {};
  const columns = options.columns === "full" ? 12 : (options.columns ?? 12);
  el.style.gridColumn = `span ${columns}`;
  if (typeof options.rows === "number") {
    el.style.gridRow = `span ${options.rows}`;
    el.style.height = `${options.rows * 56 + (options.rows - 1) * 8}px`;
  } else {
    el.style.gridRow = "auto";
    el.style.alignSelf = "start";
  }
  grid.append(el);
  await el.updateComplete;
  return el;
};
