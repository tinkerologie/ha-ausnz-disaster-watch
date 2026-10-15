var e=globalThis,t=e.ShadowRoot&&(e.ShadyCSS===void 0||e.ShadyCSS.nativeShadow)&&`adoptedStyleSheets`in Document.prototype&&`replace`in CSSStyleSheet.prototype,n=Symbol(),r=new WeakMap,i=class{constructor(e,t,r){if(this._$cssResult$=!0,r!==n)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=e,this.t=t}get styleSheet(){let e=this.o,n=this.t;if(t&&e===void 0){let t=n!==void 0&&n.length===1;t&&(e=r.get(n)),e===void 0&&((this.o=e=new CSSStyleSheet).replaceSync(this.cssText),t&&r.set(n,e))}return e}toString(){return this.cssText}},a=e=>new i(typeof e==`string`?e:e+``,void 0,n),o=(e,...t)=>new i(e.length===1?e[0]:t.reduce((t,n,r)=>t+(e=>{if(!0===e._$cssResult$)return e.cssText;if(typeof e==`number`)return e;throw Error(`Value passed to 'css' function must be a 'css' function result: `+e+`. Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.`)})(n)+e[r+1],e[0]),e,n),s=(n,r)=>{if(t)n.adoptedStyleSheets=r.map(e=>e instanceof CSSStyleSheet?e:e.styleSheet);else for(let t of r){let r=document.createElement(`style`),i=e.litNonce;i!==void 0&&r.setAttribute(`nonce`,i),r.textContent=t.cssText,n.appendChild(r)}},c=t?e=>e:e=>e instanceof CSSStyleSheet?(e=>{let t=``;for(let n of e.cssRules)t+=n.cssText;return a(t)})(e):e,{is:l,defineProperty:u,getOwnPropertyDescriptor:d,getOwnPropertyNames:f,getOwnPropertySymbols:p,getPrototypeOf:ee}=Object,m=globalThis,h=m.trustedTypes,g=h?h.emptyScript:``,_=m.reactiveElementPolyfillSupport,v=(e,t)=>e,y={toAttribute(e,t){switch(t){case Boolean:e=e?g:null;break;case Object:case Array:e=e==null?e:JSON.stringify(e)}return e},fromAttribute(e,t){let n=e;switch(t){case Boolean:n=e!==null;break;case Number:n=e===null?null:Number(e);break;case Object:case Array:try{n=JSON.parse(e)}catch{n=null}}return n}},b=(e,t)=>!l(e,t),x={attribute:!0,type:String,converter:y,reflect:!1,useDefault:!1,hasChanged:b};Symbol.metadata??=Symbol(`metadata`),m.litPropertyMetadata??=new WeakMap;var S=class extends HTMLElement{static addInitializer(e){this._$Ei(),(this.l??=[]).push(e)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(e,t=x){if(t.state&&(t.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(e)&&((t=Object.create(t)).wrapped=!0),this.elementProperties.set(e,t),!t.noAccessor){let n=Symbol(),r=this.getPropertyDescriptor(e,n,t);r!==void 0&&u(this.prototype,e,r)}}static getPropertyDescriptor(e,t,n){let{get:r,set:i}=d(this.prototype,e)??{get(){return this[t]},set(e){this[t]=e}};return{get:r,set(t){let a=r?.call(this);i?.call(this,t),this.requestUpdate(e,a,n)},configurable:!0,enumerable:!0}}static getPropertyOptions(e){return this.elementProperties.get(e)??x}static _$Ei(){if(this.hasOwnProperty(v(`elementProperties`)))return;let e=ee(this);e.finalize(),e.l!==void 0&&(this.l=[...e.l]),this.elementProperties=new Map(e.elementProperties)}static finalize(){if(this.hasOwnProperty(v(`finalized`)))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(v(`properties`))){let e=this.properties,t=[...f(e),...p(e)];for(let n of t)this.createProperty(n,e[n])}let e=this[Symbol.metadata];if(e!==null){let t=litPropertyMetadata.get(e);if(t!==void 0)for(let[e,n]of t)this.elementProperties.set(e,n)}this._$Eh=new Map;for(let[e,t]of this.elementProperties){let n=this._$Eu(e,t);n!==void 0&&this._$Eh.set(n,e)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(e){let t=[];if(Array.isArray(e)){let n=new Set(e.flat(1/0).reverse());for(let e of n)t.unshift(c(e))}else e!==void 0&&t.push(c(e));return t}static _$Eu(e,t){let n=t.attribute;return!1===n?void 0:typeof n==`string`?n:typeof e==`string`?e.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(e=>this.enableUpdating=e),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(e=>e(this))}addController(e){(this._$EO??=new Set).add(e),this.renderRoot!==void 0&&this.isConnected&&e.hostConnected?.()}removeController(e){this._$EO?.delete(e)}_$E_(){let e=new Map,t=this.constructor.elementProperties;for(let n of t.keys())this.hasOwnProperty(n)&&(e.set(n,this[n]),delete this[n]);e.size>0&&(this._$Ep=e)}createRenderRoot(){let e=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return s(e,this.constructor.elementStyles),e}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(e=>e.hostConnected?.())}enableUpdating(e){}disconnectedCallback(){this._$EO?.forEach(e=>e.hostDisconnected?.())}attributeChangedCallback(e,t,n){this._$AK(e,n)}_$ET(e,t){let n=this.constructor.elementProperties.get(e),r=this.constructor._$Eu(e,n);if(r!==void 0&&!0===n.reflect){let i=(n.converter?.toAttribute===void 0?y:n.converter).toAttribute(t,n.type);this._$Em=e,i==null?this.removeAttribute(r):this.setAttribute(r,i),this._$Em=null}}_$AK(e,t){let n=this.constructor,r=n._$Eh.get(e);if(r!==void 0&&this._$Em!==r){let e=n.getPropertyOptions(r),i=typeof e.converter==`function`?{fromAttribute:e.converter}:e.converter?.fromAttribute===void 0?y:e.converter;this._$Em=r;let a=i.fromAttribute(t,e.type);this[r]=a??this._$Ej?.get(r)??a,this._$Em=null}}requestUpdate(e,t,n,r=!1,i){if(e!==void 0){let a=this.constructor;if(!1===r&&(i=this[e]),n??=a.getPropertyOptions(e),!((n.hasChanged??b)(i,t)||n.useDefault&&n.reflect&&i===this._$Ej?.get(e)&&!this.hasAttribute(a._$Eu(e,n))))return;this.C(e,t,n)}!1===this.isUpdatePending&&(this._$ES=this._$EP())}C(e,t,{useDefault:n,reflect:r,wrapped:i},a){n&&!(this._$Ej??=new Map).has(e)&&(this._$Ej.set(e,a??t??this[e]),!0!==i||a!==void 0)||(this._$AL.has(e)||(this.hasUpdated||n||(t=void 0),this._$AL.set(e,t)),!0===r&&this._$Em!==e&&(this._$Eq??=new Set).add(e))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(e){Promise.reject(e)}let e=this.scheduleUpdate();return e!=null&&await e,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[e,t]of this._$Ep)this[e]=t;this._$Ep=void 0}let e=this.constructor.elementProperties;if(e.size>0)for(let[t,n]of e){let{wrapped:e}=n,r=this[t];!0!==e||this._$AL.has(t)||r===void 0||this.C(t,void 0,n,r)}}let e=!1,t=this._$AL;try{e=this.shouldUpdate(t),e?(this.willUpdate(t),this._$EO?.forEach(e=>e.hostUpdate?.()),this.update(t)):this._$EM()}catch(t){throw e=!1,this._$EM(),t}e&&this._$AE(t)}willUpdate(e){}_$AE(e){this._$EO?.forEach(e=>e.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(e)),this.updated(e)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(e){return!0}update(e){this._$Eq&&=this._$Eq.forEach(e=>this._$ET(e,this[e])),this._$EM()}updated(e){}firstUpdated(e){}};S.elementStyles=[],S.shadowRootOptions={mode:`open`},S[v(`elementProperties`)]=new Map,S[v(`finalized`)]=new Map,_?.({ReactiveElement:S}),(m.reactiveElementVersions??=[]).push(`2.1.2`);var C=globalThis,w=e=>e,T=C.trustedTypes,E=T?T.createPolicy(`lit-html`,{createHTML:e=>e}):void 0,D=`$lit$`,O=`lit$${Math.random().toFixed(9).slice(2)}$`,k=`?`+O,A=`<${k}>`,j=document,M=()=>j.createComment(``),N=e=>e===null||typeof e!=`object`&&typeof e!=`function`,P=Array.isArray,F=e=>P(e)||typeof e?.[Symbol.iterator]==`function`,I=`[ 	
\f\r]`,L=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,R=/-->/g,z=/>/g,B=RegExp(`>|${I}(?:([^\\s"'>=/]+)(${I}*=${I}*(?:[^ \t\n\f\r"'\`<>=]|("|')|))|$)`,`g`),V=/'/g,H=/"/g,U=/^(?:script|style|textarea|title)$/i,W=(e=>(t,...n)=>({_$litType$:e,strings:t,values:n}))(1),G=Symbol.for(`lit-noChange`),K=Symbol.for(`lit-nothing`),te=new WeakMap,q=j.createTreeWalker(j,129);function ne(e,t){if(!P(e)||!e.hasOwnProperty(`raw`))throw Error(`invalid template strings array`);return E===void 0?t:E.createHTML(t)}var re=(e,t)=>{let n=e.length-1,r=[],i,a=t===2?`<svg>`:t===3?`<math>`:``,o=L;for(let t=0;t<n;t++){let n=e[t],s,c,l=-1,u=0;for(;u<n.length&&(o.lastIndex=u,c=o.exec(n),c!==null);)u=o.lastIndex,o===L?c[1]===`!--`?o=R:c[1]===void 0?c[2]===void 0?c[3]!==void 0&&(o=B):(U.test(c[2])&&(i=RegExp(`</`+c[2],`g`)),o=B):o=z:o===B?c[0]===`>`?(o=i??L,l=-1):c[1]===void 0?l=-2:(l=o.lastIndex-c[2].length,s=c[1],o=c[3]===void 0?B:c[3]===`"`?H:V):o===H||o===V?o=B:o===R||o===z?o=L:(o=B,i=void 0);let d=o===B&&e[t+1].startsWith(`/>`)?` `:``;a+=o===L?n+A:l>=0?(r.push(s),n.slice(0,l)+D+n.slice(l)+O+d):n+O+(l===-2?t:d)}return[ne(e,a+(e[n]||`<?>`)+(t===2?`</svg>`:t===3?`</math>`:``)),r]},J=class e{constructor({strings:t,_$litType$:n},r){let i;this.parts=[];let a=0,o=0,s=t.length-1,c=this.parts,[l,u]=re(t,n);if(this.el=e.createElement(l,r),q.currentNode=this.el.content,n===2||n===3){let e=this.el.content.firstChild;e.replaceWith(...e.childNodes)}for(;(i=q.nextNode())!==null&&c.length<s;){if(i.nodeType===1){if(i.hasAttributes())for(let e of i.getAttributeNames())if(e.endsWith(D)){let t=u[o++],n=i.getAttribute(e).split(O),r=/([.?@])?(.*)/.exec(t);c.push({type:1,index:a,name:r[2],strings:n,ctor:r[1]===`.`?ae:r[1]===`?`?oe:r[1]===`@`?se:Z}),i.removeAttribute(e)}else e.startsWith(O)&&(c.push({type:6,index:a}),i.removeAttribute(e));if(U.test(i.tagName)){let e=i.textContent.split(O),t=e.length-1;if(t>0){i.textContent=T?T.emptyScript:``;for(let n=0;n<t;n++)i.append(e[n],M()),q.nextNode(),c.push({type:2,index:++a});i.append(e[t],M())}}}else if(i.nodeType===8){if(i.data===k)c.push({type:2,index:a});else{let e=-1;for(;(e=i.data.indexOf(O,e+1))!==-1;)c.push({type:7,index:a}),e+=O.length-1}}a++}}static createElement(e,t){let n=j.createElement(`template`);return n.innerHTML=e,n}};function Y(e,t,n=e,r){if(t===G)return t;let i=r===void 0?n._$Cl:n._$Co?.[r],a=N(t)?void 0:t._$litDirective$;return i?.constructor!==a&&(i?._$AO?.(!1),a===void 0?i=void 0:(i=new a(e),i._$AT(e,n,r)),r===void 0?n._$Cl=i:(n._$Co??=[])[r]=i),i!==void 0&&(t=Y(e,i._$AS(e,t.values),i,r)),t}var ie=class{constructor(e,t){this._$AV=[],this._$AN=void 0,this._$AD=e,this._$AM=t}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(e){let{el:{content:t},parts:n}=this._$AD,r=(e?.creationScope??j).importNode(t,!0);q.currentNode=r;let i=q.nextNode(),a=0,o=0,s=n[0];for(;s!==void 0;){if(a===s.index){let t;s.type===2?t=new X(i,i.nextSibling,this,e):s.type===1?t=new s.ctor(i,s.name,s.strings,this,e):s.type===6&&(t=new ce(i,this,e)),this._$AV.push(t),s=n[++o]}a!==s?.index&&(i=q.nextNode(),a++)}return q.currentNode=j,r}p(e){let t=0;for(let n of this._$AV)n!==void 0&&(n.strings===void 0?n._$AI(e[t]):(n._$AI(e,n,t),t+=n.strings.length-2)),t++}},X=class e{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(e,t,n,r){this.type=2,this._$AH=K,this._$AN=void 0,this._$AA=e,this._$AB=t,this._$AM=n,this.options=r,this._$Cv=r?.isConnected??!0}get parentNode(){let e=this._$AA.parentNode,t=this._$AM;return t!==void 0&&e?.nodeType===11&&(e=t.parentNode),e}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(e,t=this){e=Y(this,e,t),N(e)?e===K||e==null||e===``?(this._$AH!==K&&this._$AR(),this._$AH=K):e!==this._$AH&&e!==G&&this._(e):e._$litType$===void 0?e.nodeType===void 0?F(e)?this.k(e):this._(e):this.T(e):this.$(e)}O(e){return this._$AA.parentNode.insertBefore(e,this._$AB)}T(e){this._$AH!==e&&(this._$AR(),this._$AH=this.O(e))}_(e){this._$AH!==K&&N(this._$AH)?this._$AA.nextSibling.data=e:this.T(j.createTextNode(e)),this._$AH=e}$(e){let{values:t,_$litType$:n}=e,r=typeof n==`number`?this._$AC(e):(n.el===void 0&&(n.el=J.createElement(ne(n.h,n.h[0]),this.options)),n);if(this._$AH?._$AD===r)this._$AH.p(t);else{let e=new ie(r,this),n=e.u(this.options);e.p(t),this.T(n),this._$AH=e}}_$AC(e){let t=te.get(e.strings);return t===void 0&&te.set(e.strings,t=new J(e)),t}k(t){P(this._$AH)||(this._$AH=[],this._$AR());let n=this._$AH,r,i=0;for(let a of t)i===n.length?n.push(r=new e(this.O(M()),this.O(M()),this,this.options)):r=n[i],r._$AI(a),i++;i<n.length&&(this._$AR(r&&r._$AB.nextSibling,i),n.length=i)}_$AR(e=this._$AA.nextSibling,t){for(this._$AP?.(!1,!0,t);e!==this._$AB;){let t=w(e).nextSibling;w(e).remove(),e=t}}setConnected(e){this._$AM===void 0&&(this._$Cv=e,this._$AP?.(e))}},Z=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(e,t,n,r,i){this.type=1,this._$AH=K,this._$AN=void 0,this.element=e,this.name=t,this._$AM=r,this.options=i,n.length>2||n[0]!==``||n[1]!==``?(this._$AH=Array(n.length-1).fill(new String),this.strings=n):this._$AH=K}_$AI(e,t=this,n,r){let i=this.strings,a=!1;if(i===void 0)e=Y(this,e,t,0),a=!N(e)||e!==this._$AH&&e!==G,a&&(this._$AH=e);else{let r=e,o,s;for(e=i[0],o=0;o<i.length-1;o++)s=Y(this,r[n+o],t,o),s===G&&(s=this._$AH[o]),a||=!N(s)||s!==this._$AH[o],s===K?e=K:e!==K&&(e+=(s??``)+i[o+1]),this._$AH[o]=s}a&&!r&&this.j(e)}j(e){e===K?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,e??``)}},ae=class extends Z{constructor(){super(...arguments),this.type=3}j(e){this.element[this.name]=e===K?void 0:e}},oe=class extends Z{constructor(){super(...arguments),this.type=4}j(e){this.element.toggleAttribute(this.name,!!e&&e!==K)}},se=class extends Z{constructor(e,t,n,r,i){super(e,t,n,r,i),this.type=5}_$AI(e,t=this){if((e=Y(this,e,t,0)??K)===G)return;let n=this._$AH,r=e===K&&n!==K||e.capture!==n.capture||e.once!==n.once||e.passive!==n.passive,i=e!==K&&(n===K||r);r&&this.element.removeEventListener(this.name,this,n),i&&this.element.addEventListener(this.name,this,e),this._$AH=e}handleEvent(e){typeof this._$AH==`function`?this._$AH.call(this.options?.host??this.element,e):this._$AH.handleEvent(e)}},ce=class{constructor(e,t,n){this.element=e,this.type=6,this._$AN=void 0,this._$AM=t,this.options=n}get _$AU(){return this._$AM._$AU}_$AI(e){Y(this,e)}},le=C.litHtmlPolyfillSupport;le?.(J,X),(C.litHtmlVersions??=[]).push(`3.3.3`);var ue=(e,t,n)=>{let r=n?.renderBefore??t,i=r._$litPart$;if(i===void 0){let e=n?.renderBefore??null;r._$litPart$=i=new X(t.insertBefore(M(),e),e,void 0,n??{})}return i._$AI(e),i},Q=globalThis,$=class extends S{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let e=super.createRenderRoot();return this.renderOptions.renderBefore??=e.firstChild,e}update(e){let t=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(e),this._$Do=ue(t,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return G}};$._$litElement$=!0,$.finalized=!0,Q.litElementHydrateSupport?.({LitElement:$});var de=Q.litElementPolyfillSupport;de?.({LitElement:$}),(Q.litElementVersions??=[]).push(`4.2.2`);var fe=class extends ${_config;_hass;_filter=`all`;_activeTab=`none`;static properties={_config:{state:!0},_hass:{state:!0},_filter:{state:!0},_activeTab:{state:!0}};static styles=o`
    :host {
      display: block;
    }
    ha-card {
      padding: 16px;
      border-radius: var(--ha-card-border-radius, 12px);
      box-shadow: var(--ha-card-box-shadow, 0 2px 8px rgba(0, 0, 0, 0.1));
      background: var(--ha-card-background, var(--card-background-color, #fff));
      color: var(--primary-text-color, #212121);
      font-family: var(--paper-font-body1_-_font-family, Roboto, sans-serif);
      overflow: hidden;
    }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
    }
    .title {
      font-size: 1.15rem;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .banner {
      padding: 12px 16px;
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-weight: 600;
      margin-bottom: 14px;
      color: #fff;
      transition: background-color 0.3s ease;
    }
    .banner-emergency {
      background: #d32f2f;
      animation: pulse 2s infinite;
    }
    .banner-watch-and-act {
      background: #e65100;
    }
    .banner-advice {
      background: #f57f17;
      color: #212121;
    }
    .banner-clear {
      background: #2e7d32;
    }
    @keyframes pulse {
      0% {
        box-shadow: 0 0 0 0 rgba(211, 47, 47, 0.6);
      }
      70% {
        box-shadow: 0 0 0 10px rgba(211, 47, 47, 0);
      }
      100% {
        box-shadow: 0 0 0 0 rgba(211, 47, 47, 0);
      }
    }

    /* Top 4 Dashboard Metric Tiles */
    .dashboard-tiles {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 8px;
      margin-bottom: 14px;
    }
    @media (min-width: 480px) {
      .dashboard-tiles {
        grid-template-columns: repeat(4, 1fr);
      }
    }
    .dash-tile {
      border-radius: 8px;
      padding: 10px 12px;
      color: #ffffff;
      cursor: pointer;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      transition: transform 0.15s ease, filter 0.15s ease;
      min-height: 64px;
      user-select: none;
    }
    .dash-tile:hover {
      transform: translateY(-2px);
      filter: brightness(1.08);
    }
    .dash-tile.active {
      outline: 2px solid #ffffff;
      box-shadow: 0 0 8px rgba(0, 0, 0, 0.3);
    }
    .dash-tile-news {
      background: #c14619;
    }
    .dash-tile-power {
      background: #004a89;
    }
    .dash-tile-roads {
      background: #43525a;
    }
    .dash-tile-weather {
      background: #125b26;
    }
    .dash-tile-title {
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .dash-tile-value {
      font-size: 1.35rem;
      font-weight: 700;
      margin-top: 4px;
      display: flex;
      align-items: baseline;
      gap: 4px;
    }
    .dash-tile-sub {
      font-size: 0.7rem;
      opacity: 0.9;
    }

    /* Quick Action Buttons (Relief, Cameras, Telemetry) */
    .quick-actions {
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
      margin-bottom: 14px;
    }
    .action-btn {
      background: var(--secondary-background-color, #f0f0f0);
      color: var(--primary-text-color, #212121);
      border: 1px solid var(--divider-color, #e0e0e0);
      border-radius: 6px;
      padding: 6px 10px;
      font-size: 0.78rem;
      font-weight: 600;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      transition: all 0.2s ease;
      user-select: none;
    }
    .action-btn:hover {
      background: var(--primary-color, #0288d1);
      color: #fff;
      border-color: var(--primary-color, #0288d1);
    }
    .action-btn.active {
      background: var(--primary-color, #0288d1);
      color: #fff;
      border-color: var(--primary-color, #0288d1);
    }

    /* Drawer / Expanded Section */
    .drawer-content {
      background: var(--secondary-background-color, #fafafa);
      border: 1px solid var(--divider-color, #e0e0e0);
      border-radius: 8px;
      padding: 12px;
      margin-bottom: 14px;
      animation: fadeIn 0.2s ease;
    }
    @keyframes fadeIn {
      from {
        opacity: 0;
        transform: translateY(-4px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }
    .drawer-header {
      font-weight: 700;
      font-size: 0.9rem;
      margin-bottom: 8px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid var(--divider-color, #e0e0e0);
      padding-bottom: 4px;
    }
    .drawer-close {
      cursor: pointer;
      font-size: 1rem;
      line-height: 1;
    }

    /* Outage & Road Item Cards */
    .detail-list {
      display: flex;
      flex-direction: column;
      gap: 6px;
      max-height: 260px;
      overflow-y: auto;
    }
    .detail-card {
      background: var(--card-background-color, #fff);
      border: 1px solid var(--divider-color, #e0e0e0);
      border-radius: 6px;
      padding: 8px 10px;
      font-size: 0.8rem;
    }
    .detail-card-title {
      font-weight: 600;
      margin-bottom: 3px;
    }
    .detail-card-meta {
      color: var(--secondary-text-color, #666);
      font-size: 0.72rem;
    }

    /* Telemetry Grid (Weather, Fire Danger, Air Quality) */
    .telemetry-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
      gap: 8px;
      margin-top: 6px;
    }
    .telemetry-card {
      background: var(--card-background-color, #fff);
      border: 1px solid var(--divider-color, #e0e0e0);
      border-radius: 6px;
      padding: 8px;
      text-align: center;
    }
    .telemetry-card-label {
      font-size: 0.7rem;
      color: var(--secondary-text-color, #666);
      text-transform: uppercase;
    }
    .telemetry-card-val {
      font-size: 1.1rem;
      font-weight: 700;
      margin-top: 2px;
    }
    .fdr-badge {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 12px;
      font-weight: 700;
      font-size: 0.75rem;
      margin-top: 4px;
      color: #fff;
    }
    .fdr-moderate {
      background: #2e7d32;
    }
    .fdr-high {
      background: #f57f17;
    }
    .fdr-extreme {
      background: #e65100;
    }
    .fdr-catastrophic {
      background: #b71c1c;
    }

    /* Camera Grid */
    .camera-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 8px;
      max-height: 280px;
      overflow-y: auto;
    }
    .camera-card {
      background: var(--card-background-color, #fff);
      border: 1px solid var(--divider-color, #e0e0e0);
      border-radius: 6px;
      overflow: hidden;
      font-size: 0.75rem;
    }
    .camera-img {
      width: 100%;
      height: 90px;
      object-fit: cover;
      background: #333;
      display: block;
    }
    .camera-label {
      padding: 4px 6px;
      font-weight: 600;
      text-overflow: ellipsis;
      overflow: hidden;
      white-space: nowrap;
    }

    /* Nearby Council Links */
    .council-links {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-top: 6px;
    }
    .council-chip {
      background: var(--card-background-color, #fff);
      border: 1px solid var(--divider-color, #e0e0e0);
      border-radius: 14px;
      padding: 4px 10px;
      font-size: 0.75rem;
      text-decoration: none;
      color: var(--primary-color, #0288d1);
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }
    .council-chip:hover {
      background: var(--secondary-background-color, #f0f0f0);
    }

    /* Filter Chips */
    .filters {
      display: flex;
      gap: 6px;
      margin-bottom: 10px;
      overflow-x: auto;
      padding-bottom: 2px;
    }
    .filter-chip {
      background: var(--secondary-background-color, #f0f0f0);
      border: 1px solid var(--divider-color, #e0e0e0);
      border-radius: 16px;
      padding: 4px 10px;
      font-size: 0.75rem;
      cursor: pointer;
      user-select: none;
      transition: all 0.2s ease;
      white-space: nowrap;
    }
    .filter-chip.active {
      background: var(--primary-color, #0288d1);
      color: #fff;
      border-color: var(--primary-color, #0288d1);
    }

    /* Incidents List */
    .incidents-list {
      display: flex;
      flex-direction: column;
      gap: 8px;
      max-height: 340px;
      overflow-y: auto;
    }
    .incident-item {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 10px 12px;
      background: var(--secondary-background-color, #fafafa);
      border-left: 4px solid var(--divider-color, #e0e0e0);
      border-radius: 4px;
      text-decoration: none;
      color: inherit;
      transition: transform 0.15s ease, background 0.15s ease;
    }
    .incident-item:hover {
      background: var(--table-row-hover-color, #f0f4f8);
      transform: translateX(2px);
    }
    .incident-item.emergency {
      border-left-color: #d32f2f;
    }
    .incident-item.watch-act {
      border-left-color: #e65100;
    }
    .incident-item.advice {
      border-left-color: #fbc02d;
    }
    .incident-main {
      flex: 1;
      margin-right: 12px;
    }
    .incident-title {
      font-size: 0.88rem;
      font-weight: 600;
      line-height: 1.25;
    }
    .incident-sub {
      font-size: 0.72rem;
      color: var(--secondary-text-color, #757575);
      margin-top: 3px;
    }
    .incident-meta {
      text-align: right;
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      gap: 3px;
    }
    .badge {
      font-size: 0.68rem;
      padding: 2px 7px;
      border-radius: 10px;
      font-weight: 600;
      text-transform: uppercase;
    }
    .badge-emergency {
      background: #ffebee;
      color: #c62828;
    }
    .badge-watch-act {
      background: #fff3e0;
      color: #ef6c00;
    }
    .badge-advice {
      background: #fffde7;
      color: #f57f17;
    }
    .badge-info {
      background: #e3f2fd;
      color: #1565c0;
    }
    .distance-tag {
      font-size: 0.78rem;
      font-weight: 600;
      color: var(--primary-color, #0288d1);
    }
    .footer {
      display: flex;
      justify-content: flex-end;
      margin-top: 12px;
      padding-top: 8px;
      border-top: 1px solid var(--divider-color, #e0e0e0);
    }
    .btn-map {
      background: var(--primary-color, #03a9f4);
      color: #fff;
      border: none;
      padding: 7px 14px;
      border-radius: 6px;
      font-weight: 600;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      text-decoration: none;
      font-size: 0.82rem;
    }
    .empty-state {
      padding: 16px 10px;
      text-align: center;
      color: var(--secondary-text-color, #757575);
      font-size: 0.85rem;
    }
  `;setConfig(e){this._config={title:`Australia and New Zealand Disaster Watch`,max_incidents:10,show_map_button:!0,...e}}set hass(e){this._hass=e}getCardSize(){return 7}static getStubConfig(){return{type:`custom:ausnz-disaster-card`,title:`Australia and New Zealand Disaster Watch`,max_incidents:10,show_map_button:!0}}_findEntity(e,t=!0){if(!this._hass)return null;let n=this._hass.entities??{},r=Object.keys(this._hass.states).find(t=>t.startsWith(`sensor.`)&&t.endsWith(`_${e}`)&&n[t]?.platform===`ausnz_disaster_watch`);return r||=Object.keys(this._hass.states).find(t=>{if(!t.startsWith(`sensor.`)||!t.endsWith(`_${e}`))return!1;let n=this._hass.states[t],r=n?.attributes?.attribution||``;return r.includes(`Disaster Watch`)||r.includes(`Emergency Services`)||n?.attributes?.integration===`ausnz_disaster_watch`}),!r&&t&&(r=Object.keys(this._hass.states).find(t=>t.startsWith(`sensor.`)&&t.endsWith(`_${e}`))),r?this._hass.states[r]:null}_getNearbyIncidents(){if(!this._hass)return[];let e=[];for(let[t,n]of Object.entries(this._hass.states))t.startsWith(`geo_location.`)&&n.attributes&&(n.attributes.integration===`ausnz_disaster_watch`||n.attributes.integration===`australian_disaster_watch`||n.attributes.source?.includes(`ausnz_disaster_watch`)||n.attributes.source?.includes(`australian_disaster_watch`))&&e.push({id:t,title:n.state||n.attributes.title||`Emergency Incident`,hazard_type:n.attributes.hazard_type||`Other`,warning_level:n.attributes.warning_level||`Information`,distance_km:n.attributes.distance_km||n.attributes.distance,location_name:n.attributes.location_name,responsible_agency:n.attributes.responsible_agency||n.attributes.source,web_url:n.attributes.web_url,status:n.attributes.status,updated_at:n.attributes.updated_at});return e.sort((e,t)=>(e.distance_km??9999)-(t.distance_km??9999)),e}_toggleTab(e){this._activeTab=this._activeTab===e?`none`:e}render(){if(!this._hass)return W`<ha-card><div class="empty-state">Loading...</div></ha-card>`;let e=this._findEntity(`highest_warning_level`),t=this._findEntity(`active_hazards_count`),n=this._findEntity(`power_outages_count`),r=this._findEntity(`road_closures_count`),i=this._findEntity(`weather_warnings_count`),a=this._findEntity(`fire_danger_rating`),o=this._findEntity(`air_quality`),s=this._findEntity(`local_weather_observation`,!1)||this._findEntity(`primary_weather_observation`),c=this._findEntity(`relief_facilities_count`),l=e?.state||`All Clear`,u=t&&parseInt(t.state,10)||0,d=n&&parseInt(n.state,10)||0,f=r&&parseInt(r.state,10)||0,p=i&&parseInt(i.state,10)||0,ee=c&&parseInt(c.state,10)||0,m=n?.attributes?.customers_affected||0,h=n?.attributes?.outages||[],g=r?.attributes?.closures||[],_=i?.attributes?.warnings||[],v=c?.attributes?.facilities||[],y=`banner-clear`,b=`ALL CLEAR — NO ACTIVE THREATS`,x=`🛡️`;l===`Emergency Warning`?(y=`banner-emergency`,b=`EMERGENCY WARNING IN REGION`,x=`🚨`):l===`Watch and Act`?(y=`banner-watch-and-act`,b=`WATCH AND ACT IN REGION`,x=`⚠️`):l===`Advice`&&(y=`banner-advice`,b=`ADVICE LEVEL ACTIVE`,x=`ℹ️`);let S=this._getNearbyIncidents(),C=S;this._filter===`fire`?C=S.filter(e=>e.hazard_type.toLowerCase().includes(`fire`)):this._filter===`weather`?C=S.filter(e=>[`flood`,`storm`,`cyclone`].some(t=>e.hazard_type.toLowerCase().includes(t))):this._filter===`road`&&(C=S.filter(e=>e.hazard_type.toLowerCase().includes(`road`)));let w=this._config?.max_incidents||10,T=C.slice(0,w),E=s?.state===void 0?`--`:`${s.state}°C`,D=s?.attributes?.relative_humidity?`${s.attributes.relative_humidity}%`:`--`,O=s?.attributes?.pressure_hpa?`${s.attributes.pressure_hpa} hPa`:`--`,k=s?.attributes?.wind_speed_avg_kph?`${s.attributes.wind_speed_avg_kph} km/h`:`--`,A=a?.state&&a.state!==`unknown`&&a.state!==`unavailable`?a.state:`--`,j=o?.state&&o.state!==`unknown`&&o.state!==`unavailable`?o.state:`--`,M=i?.attributes?.emergency_news||e?.attributes?.emergency_news||[],N=M.length,P=i?.attributes?.nearby_councils||e?.attributes?.nearby_councils||[],F=Object.entries(this._hass.states).filter(([e,t])=>{if(!e.startsWith(`camera.`))return!1;let n=this._hass.entities??{};return n[e]?.platform===`ausnz_disaster_watch`||n[e]?.platform===`australian_disaster_watch`||t.attributes?.integration===`ausnz_disaster_watch`||t.attributes?.integration===`australian_disaster_watch`||e.includes(`disaster_watch`)}).map(([e,t])=>({entityId:e,name:t.attributes.friendly_name||t.attributes.name||e.replace(`camera.`,``)}));return W`
      <ha-card>
        <div class="header">
          <div class="title">
            <span>🚨</span>
            <span>${this._config?.title||`Australia and New Zealand Disaster Watch`}</span>
          </div>
        </div>

        <div class="banner ${y}">
          <span>${x} ${b}</span>
          <span>${u} active hazards</span>
        </div>

        <!-- 4 Top Metric Tiles (Emergency News, Power Outages, Road Conditions, Weather Warnings) -->
        <div class="dashboard-tiles">
          <div
            class="dash-tile dash-tile-news ${this._activeTab===`news`?`active`:``}"
            @click=${()=>this._toggleTab(`news`)}
          >
            <div class="dash-tile-title">
              <span>📰</span>
              <span>Emergency News</span>
            </div>
            <div class="dash-tile-value">
              <span>${N}</span>
              <span class="dash-tile-sub">Bulletins</span>
            </div>
          </div>

          <div
            class="dash-tile dash-tile-power ${this._activeTab===`outages`?`active`:``}"
            @click=${()=>this._toggleTab(`outages`)}
          >
            <div class="dash-tile-title">
              <span>⚡</span>
              <span>Power Outages</span>
            </div>
            <div class="dash-tile-value">
              <span>${d}</span>
              <span class="dash-tile-sub">(${m} affected)</span>
            </div>
          </div>

          <div
            class="dash-tile dash-tile-roads ${this._activeTab===`roads`?`active`:``}"
            @click=${()=>this._toggleTab(`roads`)}
          >
            <div class="dash-tile-title">
              <span>🚧</span>
              <span>Road Conditions</span>
            </div>
            <div class="dash-tile-value">
              <span>${f}</span>
              <span class="dash-tile-sub">Closures</span>
            </div>
          </div>

          <div
            class="dash-tile dash-tile-weather ${this._activeTab===`warnings`?`active`:``}"
            @click=${()=>this._toggleTab(`warnings`)}
          >
            <div class="dash-tile-title">
              <span>⛈️</span>
              <span>Weather Warnings</span>
            </div>
            <div class="dash-tile-value">
              <span>${p}</span>
              <span class="dash-tile-sub">BoM Alerts</span>
            </div>
          </div>
        </div>

        <!-- Quick Action Buttons -->
        <div class="quick-actions">
          <button
            class="action-btn ${this._activeTab===`telemetry`?`active`:``}"
            @click=${()=>this._toggleTab(`telemetry`)}
          >
            <span>🌡️</span>
            <span>Conditions & AFDRS</span>
          </button>

          <button
            class="action-btn ${this._activeTab===`cameras`?`active`:``}"
            @click=${()=>this._toggleTab(`cameras`)}
          >
            <span>📹</span>
            <span>Flood Cameras (${F.length})</span>
          </button>

          <button
            class="action-btn ${this._activeTab===`relief`?`active`:``}"
            @click=${()=>this._toggleTab(`relief`)}
          >
            <span>🏠</span>
            <span>Relief & Evac (${ee})</span>
          </button>

          <button
            class="action-btn ${this._activeTab===`councils`?`active`:``}"
            @click=${()=>this._toggleTab(`councils`)}
          >
            <span>🏛️</span>
            <span>Nearby Councils (${P.length})</span>
          </button>
        </div>

        <!-- Expandable Drawer for Active Tab -->
        ${this._activeTab===`none`?``:W`
              <div class="drawer-content">
                ${this._activeTab===`news`?W`
                      <div class="drawer-header">
                        <span>📰 Emergency Bulletins & News (${N})</span>
                        <span class="drawer-close" @click=${()=>this._activeTab=`none`}>✕</span>
                      </div>
                      <div class="detail-list">
                        ${M.length===0?W`<div class="empty-state">No active emergency news or bulletins published.</div>`:M.map(e=>W`
                                <div class="detail-card">
                                  <div class="detail-card-title">${e.title||`Disaster News`}</div>
                                  ${e.description?W`<div class="detail-card-meta">${e.description}</div>`:``}
                                  ${e.link?W`<div class="detail-card-meta"><a href="${e.link}" target="_blank" rel="noreferrer" style="color:var(--primary-color);">Read official release →</a></div>`:``}
                                </div>
                              `)}
                      </div>
                    `:``}

                ${this._activeTab===`outages`?W`
                      <div class="drawer-header">
                        <span>⚡ Power Outages (${d} active — ${m} customers affected)</span>
                        <span class="drawer-close" @click=${()=>this._activeTab=`none`}>✕</span>
                      </div>
                      <div class="detail-list">
                        ${h.length===0?W`<div class="empty-state">No power outages reported in monitored area.</div>`:h.map(e=>W`
                                <div class="detail-card">
                                  <div class="detail-card-title">${e.suburb||`Local Suburb`} — ${e.cause}</div>
                                  <div class="detail-card-meta">
                                    Customers: ${e.customers_affected} • Estimated Restoration: ${e.restore_time||`Pending`}
                                  </div>
                                </div>
                              `)}
                      </div>
                    `:``}

                ${this._activeTab===`roads`?W`
                      <div class="drawer-header">
                        <span>🚧 Road Conditions & Closures (${f})</span>
                        <span class="drawer-close" @click=${()=>this._activeTab=`none`}>✕</span>
                      </div>
                      <div class="detail-list">
                        ${g.length===0?W`<div class="empty-state">No road closures reported in monitored area.</div>`:g.map(e=>W`
                                <div class="detail-card">
                                  <div class="detail-card-title">${e.road} (${e.suburb||`Region`}) — ${e.status}</div>
                                  <div class="detail-card-meta">
                                    Reason: ${e.reason||`Hazard`} • Agency: ${e.source} ${e.advice?`• Advice: ${e.advice}`:``}
                                  </div>
                                </div>
                              `)}
                      </div>
                    `:``}

                ${this._activeTab===`warnings`?W`
                      <div class="drawer-header">
                        <span>⛈️ Bureau of Meteorology Warnings (${p})</span>
                        <span class="drawer-close" @click=${()=>this._activeTab=`none`}>✕</span>
                      </div>
                      <div class="detail-list">
                        ${_.length===0?W`<div class="empty-state">No weather warnings currently active.</div>`:_.map(e=>W`
                                <div class="detail-card">
                                  <div class="detail-card-title">
                                    <a href="${e.link||`#`}" target="_blank" rel="noreferrer" style="color:inherit;text-decoration:underline;">
                                      ${e.title}
                                    </a>
                                  </div>
                                  <div class="detail-card-meta">Districts: ${e.locations||`Forecast Area`}</div>
                                </div>
                              `)}
                      </div>
                    `:``}

                ${this._activeTab===`telemetry`?W`
                      <div class="drawer-header">
                        <span>🌡️ Environmental Telemetry & Fire Danger</span>
                        <span class="drawer-close" @click=${()=>this._activeTab=`none`}>✕</span>
                      </div>
                      <div class="telemetry-grid">
                        <div class="telemetry-card">
                          <div class="telemetry-card-label">Air Temp</div>
                          <div class="telemetry-card-val">${E}</div>
                        </div>
                        <div class="telemetry-card">
                          <div class="telemetry-card-label">Humidity</div>
                          <div class="telemetry-card-val">${D}</div>
                        </div>
                        <div class="telemetry-card">
                          <div class="telemetry-card-label">Pressure</div>
                          <div class="telemetry-card-val">${O}</div>
                        </div>
                        <div class="telemetry-card">
                          <div class="telemetry-card-label">Wind Speed</div>
                          <div class="telemetry-card-val">${k}</div>
                        </div>
                        <div class="telemetry-card">
                          <div class="telemetry-card-label">Fire Danger (AFDRS)</div>
                          <span class="fdr-badge ${A.toLowerCase().includes(`catastrophic`)?`fdr-catastrophic`:A.toLowerCase().includes(`extreme`)?`fdr-extreme`:A.toLowerCase().includes(`high`)?`fdr-high`:`fdr-moderate`}">${A}</span>
                        </div>
                        <div class="telemetry-card">
                          <div class="telemetry-card-label">Air Quality</div>
                          <div class="telemetry-card-val" style="color:#2e7d32;">${j}</div>
                        </div>
                      </div>
                    `:``}

                ${this._activeTab===`cameras`?W`
                      <div class="drawer-header">
                        <span>📹 Live Flood & Traffic Webcams (${F.length})</span>
                        <span class="drawer-close" @click=${()=>this._activeTab=`none`}>✕</span>
                      </div>
                      ${F.length===0?W`<div class="detail-list"><div class="empty-state">No live flood or traffic cameras available for this jurisdiction.</div></div>`:W`
                            <div class="camera-grid">
                              ${F.map(e=>W`
                                  <div class="camera-card">
                                    <img
                                      class="camera-img"
                                      src="/api/camera_proxy/${e.entityId}"
                                      alt="${e.name}"
                                      loading="lazy"
                                    />
                                    <div class="camera-label">${e.name}</div>
                                  </div>
                                `)}
                            </div>
                          `}
                    `:``}

                ${this._activeTab===`relief`?W`
                      <div class="drawer-header">
                        <span>🏠 Disaster Relief Facilities</span>
                        <span class="drawer-close" @click=${()=>this._activeTab=`none`}>✕</span>
                      </div>
                      <div class="detail-list">
                        ${v.length===0?W`<div class="empty-state">No open relief facilities or evacuations required at this time.</div>`:v.map(e=>W`
                                <div class="detail-card">
                                  <div class="detail-card-title">${e.name} (${e.suburb||`Region`})</div>
                                  <div class="detail-card-meta">Address: ${e.address||`Council Depot`} • Status: ${e.status}</div>
                                </div>
                              `)}
                      </div>
                    `:``}

                ${this._activeTab===`councils`?W`
                      <div class="drawer-header">
                        <span>🏛️ Connected Australian Disaster Dashboards (${P.length})</span>
                        <span class="drawer-close" @click=${()=>this._activeTab=`none`}>✕</span>
                      </div>
                      ${P.length===0?W`<div class="detail-list"><div class="empty-state">No neighboring council disaster dashboards configured for this jurisdiction.</div></div>`:W`
                            <div class="council-links">
                              ${P.map(e=>W`
                                  <a class="council-chip" href="${e.url}" target="_blank" rel="noreferrer">
                                    <span>📍</span> ${e.name}
                                  </a>
                                `)}
                            </div>
                          `}
                    `:``}
              </div>
            `}

        <!-- Filter Chips for Incident List -->
        <div class="filters">
          <div
            class="filter-chip ${this._filter===`all`?`active`:``}"
            @click=${()=>this._filter=`all`}
          >
            All Hazards (${S.length})
          </div>
          <div
            class="filter-chip ${this._filter===`fire`?`active`:``}"
            @click=${()=>this._filter=`fire`}
          >
            Fires
          </div>
          <div
            class="filter-chip ${this._filter===`weather`?`active`:``}"
            @click=${()=>this._filter=`weather`}
          >
            Weather / Flood
          </div>
          <div
            class="filter-chip ${this._filter===`road`?`active`:``}"
            @click=${()=>this._filter=`road`}
          >
            Roads
          </div>
        </div>

        <!-- Incidents List -->
        <div class="incidents-list">
          ${T.length===0?W`<div class="empty-state">
                No active incidents found in this filter within the monitored radius.
              </div>`:T.map(e=>{let t=`badge-info`,n=``;return e.warning_level===`Emergency Warning`?(t=`badge-emergency`,n=`emergency`):e.warning_level===`Watch and Act`?(t=`badge-watch-act`,n=`watch-act`):e.warning_level===`Advice`&&(t=`badge-advice`,n=`advice`),W`
                  <a
                    class="incident-item ${n}"
                    href="${e.web_url||`/map`}"
                    target="${e.web_url?`_blank`:`_self`}"
                    rel="noreferrer"
                  >
                    <div class="incident-main">
                      <div class="incident-title">${e.title}</div>
                      <div class="incident-sub">
                        ${e.hazard_type} • ${e.responsible_agency||`Emergency Agency`}
                        ${e.location_name?`• ${e.location_name}`:``}
                      </div>
                    </div>
                    <div class="incident-meta">
                      <span class="badge ${t}">${e.warning_level}</span>
                      ${e.distance_km===void 0?``:W`<span class="distance-tag">${e.distance_km} km</span>`}
                    </div>
                  </a>
                `})}
        </div>

        ${this._config?.show_map_button?W`
              <div class="footer">
                <a class="btn-map" href="/map">
                  <span>🗺️</span>
                  <span>View Incidents on Map</span>
                </a>
              </div>
            `:``}
      </ha-card>
    `}};customElements.get(`ausnz-disaster-card`)||customElements.define(`ausnz-disaster-card`,fe),customElements.get(`aus-disaster-card`)||customElements.define(`aus-disaster-card`,fe),window.customCards=window.customCards||[],window.customCards.some(e=>e.type===`ausnz-disaster-card`)||window.customCards.push({type:`ausnz-disaster-card`,name:`Australia and New Zealand Disaster Watch Card`,description:`Real-time Australia and New Zealand Warning System disaster monitor and proximity hazard tracker.`,preview:!0,documentationURL:`https://github.com/tinkerologie/ha-ausnz-disaster-watch`}),window.customCards.some(e=>e.type===`aus-disaster-card`)||window.customCards.push({type:`aus-disaster-card`,name:`Australia and New Zealand Disaster Watch Card (Legacy Alias)`,description:`Real-time Australia and New Zealand Warning System disaster monitor and proximity hazard tracker.`,preview:!1,documentationURL:`https://github.com/tinkerologie/ha-ausnz-disaster-watch`});