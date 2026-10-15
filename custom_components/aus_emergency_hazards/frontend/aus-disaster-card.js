/**
 * @license
 * Copyright 2019 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */const R=globalThis,L=R.ShadowRoot&&(R.ShadyCSS===void 0||R.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,D=Symbol(),V=new WeakMap;let et=class{constructor(t,e,s){if(this._$cssResult$=!0,s!==D)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=t,this.t=e}get styleSheet(){let t=this.o;const e=this.t;if(L&&t===void 0){const s=e!==void 0&&e.length===1;s&&(t=V.get(e)),t===void 0&&((this.o=t=new CSSStyleSheet).replaceSync(this.cssText),s&&V.set(e,t))}return t}toString(){return this.cssText}};const ot=r=>new et(typeof r=="string"?r:r+"",void 0,D),lt=(r,...t)=>{const e=r.length===1?r[0]:t.reduce((s,i,n)=>s+(a=>{if(a._$cssResult$===!0)return a.cssText;if(typeof a=="number")return a;throw Error("Value passed to 'css' function must be a 'css' function result: "+a+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(i)+r[n+1],r[0]);return new et(e,r,D)},ct=(r,t)=>{if(L)r.adoptedStyleSheets=t.map(e=>e instanceof CSSStyleSheet?e:e.styleSheet);else for(const e of t){const s=document.createElement("style"),i=R.litNonce;i!==void 0&&s.setAttribute("nonce",i),s.textContent=e.cssText,r.appendChild(s)}},q=L?r=>r:r=>r instanceof CSSStyleSheet?(t=>{let e="";for(const s of t.cssRules)e+=s.cssText;return ot(e)})(r):r;/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */const{is:dt,defineProperty:ht,getOwnPropertyDescriptor:pt,getOwnPropertyNames:ut,getOwnPropertySymbols:ft,getPrototypeOf:_t}=Object,H=globalThis,G=H.trustedTypes,$t=G?G.emptyScript:"",gt=H.reactiveElementPolyfillSupport,S=(r,t)=>r,I={toAttribute(r,t){switch(t){case Boolean:r=r?$t:null;break;case Object:case Array:r=r==null?r:JSON.stringify(r)}return r},fromAttribute(r,t){let e=r;switch(t){case Boolean:e=r!==null;break;case Number:e=r===null?null:Number(r);break;case Object:case Array:try{e=JSON.parse(r)}catch{e=null}}return e}},st=(r,t)=>!dt(r,t),F={attribute:!0,type:String,converter:I,reflect:!1,useDefault:!1,hasChanged:st};Symbol.metadata??=Symbol("metadata"),H.litPropertyMetadata??=new WeakMap;let A=class extends HTMLElement{static addInitializer(t){this._$Ei(),(this.l??=[]).push(t)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(t,e=F){if(e.state&&(e.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(t)&&((e=Object.create(e)).wrapped=!0),this.elementProperties.set(t,e),!e.noAccessor){const s=Symbol(),i=this.getPropertyDescriptor(t,s,e);i!==void 0&&ht(this.prototype,t,i)}}static getPropertyDescriptor(t,e,s){const{get:i,set:n}=pt(this.prototype,t)??{get(){return this[e]},set(a){this[e]=a}};return{get:i,set(a){const c=i?.call(this);n?.call(this,a),this.requestUpdate(t,c,s)},configurable:!0,enumerable:!0}}static getPropertyOptions(t){return this.elementProperties.get(t)??F}static _$Ei(){if(this.hasOwnProperty(S("elementProperties")))return;const t=_t(this);t.finalize(),t.l!==void 0&&(this.l=[...t.l]),this.elementProperties=new Map(t.elementProperties)}static finalize(){if(this.hasOwnProperty(S("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(S("properties"))){const e=this.properties,s=[...ut(e),...ft(e)];for(const i of s)this.createProperty(i,e[i])}const t=this[Symbol.metadata];if(t!==null){const e=litPropertyMetadata.get(t);if(e!==void 0)for(const[s,i]of e)this.elementProperties.set(s,i)}this._$Eh=new Map;for(const[e,s]of this.elementProperties){const i=this._$Eu(e,s);i!==void 0&&this._$Eh.set(i,e)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(t){const e=[];if(Array.isArray(t)){const s=new Set(t.flat(1/0).reverse());for(const i of s)e.unshift(q(i))}else t!==void 0&&e.push(q(t));return e}static _$Eu(t,e){const s=e.attribute;return s===!1?void 0:typeof s=="string"?s:typeof t=="string"?t.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(t=>this.enableUpdating=t),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(t=>t(this))}addController(t){(this._$EO??=new Set).add(t),this.renderRoot!==void 0&&this.isConnected&&t.hostConnected?.()}removeController(t){this._$EO?.delete(t)}_$E_(){const t=new Map,e=this.constructor.elementProperties;for(const s of e.keys())this.hasOwnProperty(s)&&(t.set(s,this[s]),delete this[s]);t.size>0&&(this._$Ep=t)}createRenderRoot(){const t=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return ct(t,this.constructor.elementStyles),t}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(t=>t.hostConnected?.())}enableUpdating(t){}disconnectedCallback(){this._$EO?.forEach(t=>t.hostDisconnected?.())}attributeChangedCallback(t,e,s){this._$AK(t,s)}_$ET(t,e){const s=this.constructor.elementProperties.get(t),i=this.constructor._$Eu(t,s);if(i!==void 0&&s.reflect===!0){const n=(s.converter?.toAttribute!==void 0?s.converter:I).toAttribute(e,s.type);this._$Em=t,n==null?this.removeAttribute(i):this.setAttribute(i,n),this._$Em=null}}_$AK(t,e){const s=this.constructor,i=s._$Eh.get(t);if(i!==void 0&&this._$Em!==i){const n=s.getPropertyOptions(i),a=typeof n.converter=="function"?{fromAttribute:n.converter}:n.converter?.fromAttribute!==void 0?n.converter:I;this._$Em=i;const c=a.fromAttribute(e,n.type);this[i]=c??this._$Ej?.get(i)??c,this._$Em=null}}requestUpdate(t,e,s,i=!1,n){if(t!==void 0){const a=this.constructor;if(i===!1&&(n=this[t]),s??=a.getPropertyOptions(t),!((s.hasChanged??st)(n,e)||s.useDefault&&s.reflect&&n===this._$Ej?.get(t)&&!this.hasAttribute(a._$Eu(t,s))))return;this.C(t,e,s)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(t,e,{useDefault:s,reflect:i,wrapped:n},a){s&&!(this._$Ej??=new Map).has(t)&&(this._$Ej.set(t,a??e??this[t]),n!==!0||a!==void 0)||(this._$AL.has(t)||(this.hasUpdated||s||(e=void 0),this._$AL.set(t,e)),i===!0&&this._$Em!==t&&(this._$Eq??=new Set).add(t))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(e){Promise.reject(e)}const t=this.scheduleUpdate();return t!=null&&await t,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(const[i,n]of this._$Ep)this[i]=n;this._$Ep=void 0}const s=this.constructor.elementProperties;if(s.size>0)for(const[i,n]of s){const{wrapped:a}=n,c=this[i];a!==!0||this._$AL.has(i)||c===void 0||this.C(i,void 0,n,c)}}let t=!1;const e=this._$AL;try{t=this.shouldUpdate(e),t?(this.willUpdate(e),this._$EO?.forEach(s=>s.hostUpdate?.()),this.update(e)):this._$EM()}catch(s){throw t=!1,this._$EM(),s}t&&this._$AE(e)}willUpdate(t){}_$AE(t){this._$EO?.forEach(e=>e.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(t)),this.updated(t)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(t){return!0}update(t){this._$Eq&&=this._$Eq.forEach(e=>this._$ET(e,this[e])),this._$EM()}updated(t){}firstUpdated(t){}};A.elementStyles=[],A.shadowRootOptions={mode:"open"},A[S("elementProperties")]=new Map,A[S("finalized")]=new Map,gt?.({ReactiveElement:A}),(H.reactiveElementVersions??=[]).push("2.1.2");/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */const W=globalThis,K=r=>r,T=W.trustedTypes,Z=T?T.createPolicy("lit-html",{createHTML:r=>r}):void 0,it="$lit$",$=`lit$${Math.random().toFixed(9).slice(2)}$`,rt="?"+$,mt=`<${rt}>`,b=document,k=()=>b.createComment(""),P=r=>r===null||typeof r!="object"&&typeof r!="function",j=Array.isArray,bt=r=>j(r)||typeof r?.[Symbol.iterator]=="function",M=`[
\f\r]`,E=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,J=/-->/g,Q=/>/g,g=RegExp(`>|${M}(?:([^\\s"'>=/]+)(${M}*=${M}*(?:[^
\f\r"'\`<>=]|("|')|))|$)`,"g"),X=/'/g,Y=/"/g,nt=/^(?:script|style|textarea|title)$/i,vt=r=>(t,...e)=>({_$litType$:r,strings:t,values:e}),y=vt(1),x=Symbol.for("lit-noChange"),u=Symbol.for("lit-nothing"),tt=new WeakMap,m=b.createTreeWalker(b,129);function at(r,t){if(!j(r)||!r.hasOwnProperty("raw"))throw Error("invalid template strings array");return Z!==void 0?Z.createHTML(t):t}const yt=(r,t)=>{const e=r.length-1,s=[];let i,n=t===2?"<svg>":t===3?"<math>":"",a=E;for(let c=0;c<e;c++){const o=r[c];let h,p,l=-1,f=0;for(;f<o.length&&(a.lastIndex=f,p=a.exec(o),p!==null);)f=a.lastIndex,a===E?p[1]==="!--"?a=J:p[1]!==void 0?a=Q:p[2]!==void 0?(nt.test(p[2])&&(i=RegExp("</"+p[2],"g")),a=g):p[3]!==void 0&&(a=g):a===g?p[0]===">"?(a=i??E,l=-1):p[1]===void 0?l=-2:(l=a.lastIndex-p[2].length,h=p[1],a=p[3]===void 0?g:p[3]==='"'?Y:X):a===Y||a===X?a=g:a===J||a===Q?a=E:(a=g,i=void 0);const _=a===g&&r[c+1].startsWith("/>")?" ":"";n+=a===E?o+mt:l>=0?(s.push(h),o.slice(0,l)+it+o.slice(l)+$+_):o+$+(l===-2?c:_)}return[at(r,n+(r[e]||"<?>")+(t===2?"</svg>":t===3?"</math>":"")),s]};class N{constructor({strings:t,_$litType$:e},s){let i;this.parts=[];let n=0,a=0;const c=t.length-1,o=this.parts,[h,p]=yt(t,e);if(this.el=N.createElement(h,s),m.currentNode=this.el.content,e===2||e===3){const l=this.el.content.firstChild;l.replaceWith(...l.childNodes)}for(;(i=m.nextNode())!==null&&o.length<c;){if(i.nodeType===1){if(i.hasAttributes())for(const l of i.getAttributeNames())if(l.endsWith(it)){const f=p[a++],_=i.getAttribute(l).split($),d=/([.?@])?(.*)/.exec(f);o.push({type:1,index:n,name:d[2],strings:_,ctor:d[1]==="."?xt:d[1]==="?"?wt:d[1]==="@"?Et:z}),i.removeAttribute(l)}else l.startsWith($)&&(o.push({type:6,index:n}),i.removeAttribute(l));if(nt.test(i.tagName)){const l=i.textContent.split($),f=l.length-1;if(f>0){i.textContent=T?T.emptyScript:"";for(let _=0;_<f;_++)i.append(l[_],k()),m.nextNode(),o.push({type:2,index:++n});i.append(l[f],k())}}}else if(i.nodeType===8)if(i.data===rt)o.push({type:2,index:n});else{let l=-1;for(;(l=i.data.indexOf($,l+1))!==-1;)o.push({type:7,index:n}),l+=$.length-1}n++}}static createElement(t,e){const s=b.createElement("template");return s.innerHTML=t,s}}function w(r,t,e=r,s){if(t===x)return t;let i=s!==void 0?e._$Co?.[s]:e._$Cl;const n=P(t)?void 0:t._$litDirective$;return i?.constructor!==n&&(i?._$AO?.(!1),n===void 0?i=void 0:(i=new n(r),i._$AT(r,e,s)),s!==void 0?(e._$Co??=[])[s]=i:e._$Cl=i),i!==void 0&&(t=w(r,i._$AS(r,t.values),i,s)),t}class At{constructor(t,e){this._$AV=[],this._$AN=void 0,this._$AD=t,this._$AM=e}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(t){const{el:{content:e},parts:s}=this._$AD,i=(t?.creationScope??b).importNode(e,!0);m.currentNode=i;let n=m.nextNode(),a=0,c=0,o=s[0];for(;o!==void 0;){if(a===o.index){let h;o.type===2?h=new O(n,n.nextSibling,this,t):o.type===1?h=new o.ctor(n,o.name,o.strings,this,t):o.type===6&&(h=new St(n,this,t)),this._$AV.push(h),o=s[++c]}a!==o?.index&&(n=m.nextNode(),a++)}return m.currentNode=b,i}p(t){let e=0;for(const s of this._$AV)s!==void 0&&(s.strings!==void 0?(s._$AI(t,s,e),e+=s.strings.length-2):s._$AI(t[e])),e++}}class O{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(t,e,s,i){this.type=2,this._$AH=u,this._$AN=void 0,this._$AA=t,this._$AB=e,this._$AM=s,this.options=i,this._$Cv=i?.isConnected??!0}get parentNode(){let t=this._$AA.parentNode;const e=this._$AM;return e!==void 0&&t?.nodeType===11&&(t=e.parentNode),t}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(t,e=this){t=w(this,t,e),P(t)?t===u||t==null||t===""?(this._$AH!==u&&this._$AR(),this._$AH=u):t!==this._$AH&&t!==x&&this._(t):t._$litType$!==void 0?this.$(t):t.nodeType!==void 0?this.T(t):bt(t)?this.k(t):this._(t)}O(t){return this._$AA.parentNode.insertBefore(t,this._$AB)}T(t){this._$AH!==t&&(this._$AR(),this._$AH=this.O(t))}_(t){this._$AH!==u&&P(this._$AH)?this._$AA.nextSibling.data=t:this.T(b.createTextNode(t)),this._$AH=t}$(t){const{values:e,_$litType$:s}=t,i=typeof s=="number"?this._$AC(t):(s.el===void 0&&(s.el=N.createElement(at(s.h,s.h[0]),this.options)),s);if(this._$AH?._$AD===i)this._$AH.p(e);else{const n=new At(i,this),a=n.u(this.options);n.p(e),this.T(a),this._$AH=n}}_$AC(t){let e=tt.get(t.strings);return e===void 0&&tt.set(t.strings,e=new N(t)),e}k(t){j(this._$AH)||(this._$AH=[],this._$AR());const e=this._$AH;let s,i=0;for(const n of t)i===e.length?e.push(s=new O(this.O(k()),this.O(k()),this,this.options)):s=e[i],s._$AI(n),i++;i<e.length&&(this._$AR(s&&s._$AB.nextSibling,i),e.length=i)}_$AR(t=this._$AA.nextSibling,e){for(this._$AP?.(!1,!0,e);t!==this._$AB;){const s=K(t).nextSibling;K(t).remove(),t=s}}setConnected(t){this._$AM===void 0&&(this._$Cv=t,this._$AP?.(t))}}class z{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(t,e,s,i,n){this.type=1,this._$AH=u,this._$AN=void 0,this.element=t,this.name=e,this._$AM=i,this.options=n,s.length>2||s[0]!==""||s[1]!==""?(this._$AH=Array(s.length-1).fill(new String),this.strings=s):this._$AH=u}_$AI(t,e=this,s,i){const n=this.strings;let a=!1;if(n===void 0)t=w(this,t,e,0),a=!P(t)||t!==this._$AH&&t!==x,a&&(this._$AH=t);else{const c=t;let o,h;for(t=n[0],o=0;o<n.length-1;o++)h=w(this,c[s+o],e,o),h===x&&(h=this._$AH[o]),a||=!P(h)||h!==this._$AH[o],h===u?t=u:t!==u&&(t+=(h??"")+n[o+1]),this._$AH[o]=h}a&&!i&&this.j(t)}j(t){t===u?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,t??"")}}class xt extends z{constructor(){super(...arguments),this.type=3}j(t){this.element[this.name]=t===u?void 0:t}}class wt extends z{constructor(){super(...arguments),this.type=4}j(t){this.element.toggleAttribute(this.name,!!t&&t!==u)}}class Et extends z{constructor(t,e,s,i,n){super(t,e,s,i,n),this.type=5}_$AI(t,e=this){if((t=w(this,t,e,0)??u)===x)return;const s=this._$AH,i=t===u&&s!==u||t.capture!==s.capture||t.once!==s.once||t.passive!==s.passive,n=t!==u&&(s===u||i);i&&this.element.removeEventListener(this.name,this,s),n&&this.element.addEventListener(this.name,this,t),this._$AH=t}handleEvent(t){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,t):this._$AH.handleEvent(t)}}class St{constructor(t,e,s){this.element=t,this.type=6,this._$AN=void 0,this._$AM=e,this.options=s}get _$AU(){return this._$AM._$AU}_$AI(t){w(this,t)}}const Ct=W.litHtmlPolyfillSupport;Ct?.(N,O),(W.litHtmlVersions??=[]).push("3.3.3");const kt=(r,t,e)=>{const s=e?.renderBefore??t;let i=s._$litPart$;if(i===void 0){const n=e?.renderBefore??null;s._$litPart$=i=new O(t.insertBefore(k(),n),n,void 0,e??{})}return i._$AI(r),i};/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */const B=globalThis;class C extends A{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){const t=super.createRenderRoot();return this.renderOptions.renderBefore??=t.firstChild,t}update(t){const e=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(t),this._$Do=kt(e,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return x}}C._$litElement$=!0,C.finalized=!0,B.litElementHydrateSupport?.({LitElement:C});const Pt=B.litElementPolyfillSupport;Pt?.({LitElement:C});(B.litElementVersions??=[]).push("4.2.2");class Nt extends C{_config;_hass;_filter="all";static properties={_config:{state:!0},_hass:{state:!0},_filter:{state:!0}};static styles=lt`
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
      margin-bottom: 16px;
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
    .stats-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 10px;
      margin-bottom: 16px;
    }
    .stat-card {
      background: var(--secondary-background-color, #f5f5f5);
      border-radius: 8px;
      padding: 10px 14px;
      display: flex;
      flex-direction: column;
    }
    .stat-label {
      font-size: 0.75rem;
      color: var(--secondary-text-color, #757575);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .stat-value {
      font-size: 1.2rem;
      font-weight: 700;
      margin-top: 4px;
    }
    .filters {
      display: flex;
      gap: 8px;
      margin-bottom: 12px;
      overflow-x: auto;
      padding-bottom: 4px;
    }
    .filter-chip {
      background: var(--secondary-background-color, #f0f0f0);
      border: 1px solid var(--divider-color, #e0e0e0);
      border-radius: 16px;
      padding: 4px 12px;
      font-size: 0.8rem;
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
    .incidents-list {
      display: flex;
      flex-direction: column;
      gap: 8px;
      max-height: 380px;
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
      font-size: 0.9rem;
      font-weight: 600;
      line-height: 1.25;
    }
    .incident-sub {
      font-size: 0.75rem;
      color: var(--secondary-text-color, #757575);
      margin-top: 3px;
    }
    .incident-meta {
      text-align: right;
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      gap: 4px;
    }
    .badge {
      font-size: 0.7rem;
      padding: 2px 8px;
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
      font-size: 0.8rem;
      font-weight: 600;
      color: var(--primary-color, #0288d1);
    }
    .footer {
      display: flex;
      justify-content: flex-end;
      margin-top: 14px;
      padding-top: 10px;
      border-top: 1px solid var(--divider-color, #e0e0e0);
    }
    .btn-map {
      background: var(--primary-color, #03a9f4);
      color: #fff;
      border: none;
      padding: 8px 16px;
      border-radius: 6px;
      font-weight: 600;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      text-decoration: none;
      font-size: 0.85rem;
    }
    .btn-map:hover {
      filter: brightness(0.9);
    }
    .empty-state {
      padding: 24px 12px;
      text-align: center;
      color: var(--secondary-text-color, #757575);
      font-size: 0.9rem;
    }
  `;setConfig(t){this._config={title:"Australian Disaster Watch",max_incidents:10,show_map_button:!0,...t}}set hass(t){this._hass=t}getCardSize(){return 6}static getStubConfig(){return{type:"custom:aus-disaster-card",title:"Australian Disaster Watch",max_incidents:10,show_map_button:!0}}_findEntity(t){if(!this._hass)return null;if(this._config?.entity&&this._hass.states[this._config.entity])return this._hass.states[this._config.entity];const e=Object.keys(this._hass.states).find(s=>s.startsWith(t));return e?this._hass.states[e]:null}_getNearbyIncidents(){if(!this._hass)return[];const t=[],e="geo_location.";for(const[s,i]of Object.entries(this._hass.states))s.startsWith(e)&&i.attributes&&(i.attributes.source?.includes("Queensland")||i.attributes.source?.includes("Disaster")||i.attributes.source?.includes("NSW")||i.attributes.source?.includes("Vic")||i.attributes.source?.includes("Bureau")||i.attributes.source?.includes("aus_emergency_hazards"))&&t.push({id:s,title:i.state||i.attributes.title||"Emergency Incident",hazard_type:i.attributes.hazard_type||"Other",warning_level:i.attributes.warning_level||"Information",distance_km:i.attributes.distance_km||i.attributes.distance,location_name:i.attributes.location_name,responsible_agency:i.attributes.responsible_agency||i.attributes.source,web_url:i.attributes.web_url,status:i.attributes.status,updated_at:i.attributes.updated_at});return t.sort((s,i)=>(s.distance_km??9999)-(i.distance_km??9999)),t}render(){if(!this._hass)return y`<ha-card><div class="empty-state">Loading...</div></ha-card>`;const t=this._findEntity("sensor.highest_warning_level"),e=this._findEntity("sensor.active_hazards_count"),s=this._findEntity("sensor.nearest_hazard_distance"),i=t?.state||"All Clear",n=e&&parseInt(e.state,10)||0,a=s?.state?`${s.state} km`:"None";let c="banner-clear",o="ALL CLEAR — NO ACTIVE THREATS",h="🛡️";i==="Emergency Warning"?(c="banner-emergency",o="EMERGENCY WARNING IN REGION",h="🚨"):i==="Watch and Act"?(c="banner-watch-and-act",o="WATCH AND ACT IN REGION",h="⚠️"):i==="Advice"&&(c="banner-advice",o="ADVICE LEVEL ACTIVE",h="ℹ️");let p=this._getNearbyIncidents(),l=p;this._filter==="fire"?l=p.filter(d=>d.hazard_type.toLowerCase().includes("fire")):this._filter==="weather"?l=p.filter(d=>["flood","storm","cyclone"].some(v=>d.hazard_type.toLowerCase().includes(v))):this._filter==="road"&&(l=p.filter(d=>d.hazard_type.toLowerCase().includes("road")));const f=this._config?.max_incidents||10,_=l.slice(0,f);return y`
      <ha-card>
        <div class="header">
          <div class="title">
            <span>🇦🇺</span>
            <span>${this._config?.title||"Australian Disaster Watch"}</span>
          </div>
        </div>

        <div class="banner ${c}">
          <span>${h} ${o}</span>
          <span>${n} active</span>
        </div>

        <div class="stats-grid">
          <div class="stat-card">
            <span class="stat-label">Nearest Hazard</span>
            <span class="stat-value">${a}</span>
          </div>
          <div class="stat-card">
            <span class="stat-label">Active in Perimeter</span>
            <span class="stat-value">${n}</span>
          </div>
        </div>

        <div class="filters">
          <div
            class="filter-chip ${this._filter==="all"?"active":""}"
            @click=${()=>this._filter="all"}
          >
            All Hazards (${p.length})
          </div>
          <div
            class="filter-chip ${this._filter==="fire"?"active":""}"
            @click=${()=>this._filter="fire"}
          >
            Fires
          </div>
          <div
            class="filter-chip ${this._filter==="weather"?"active":""}"
            @click=${()=>this._filter="weather"}
          >
            Weather / Flood
          </div>
          <div
            class="filter-chip ${this._filter==="road"?"active":""}"
            @click=${()=>this._filter="road"}
          >
            Roads
          </div>
        </div>

        <div class="incidents-list">
          ${_.length===0?y`<div class="empty-state">
                No active incidents found in this filter within the monitored radius.
              </div>`:_.map(d=>{let v="badge-info",U="";return d.warning_level==="Emergency Warning"?(v="badge-emergency",U="emergency"):d.warning_level==="Watch and Act"?(v="badge-watch-act",U="watch-act"):d.warning_level==="Advice"&&(v="badge-advice",U="advice"),y`
                  <a
                    class="incident-item ${U}"
                    href="${d.web_url||"/map"}"
                    target="${d.web_url?"_blank":"_self"}"
                    rel="noreferrer"
                  >
                    <div class="incident-main">
                      <div class="incident-title">${d.title}</div>
                      <div class="incident-sub">
                        ${d.hazard_type} • ${d.responsible_agency||"Emergency Agency"}
                        ${d.location_name?`• ${d.location_name}`:""}
                      </div>
                    </div>
                    <div class="incident-meta">
                      <span class="badge ${v}">${d.warning_level}</span>
                      ${d.distance_km!==void 0?y`<span class="distance-tag">${d.distance_km} km</span>`:""}
                    </div>
                  </a>
                `})}
        </div>

        ${this._config?.show_map_button?y`
              <div class="footer">
                <a class="btn-map" href="/map">
                  <span>🗺️</span>
                  <span>View Incidents on Map</span>
                </a>
              </div>
            `:""}
      </ha-card>
    `}}customElements.get("aus-disaster-card")||customElements.define("aus-disaster-card",Nt);window.customCards=window.customCards||[];window.customCards.push({type:"aus-disaster-card",name:"Australian Disaster Watch Card",description:"Real-time Australian Warning System disaster monitor and proximity hazard tracker.",preview:!0,documentationURL:"https://github.com/ruaandeysel/ha-australian-disaster-watch"});
