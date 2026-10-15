/**
 * @license
 * Copyright 2019 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */const L=globalThis,F=L.ShadowRoot&&(L.ShadyCSS===void 0||L.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,G=Symbol(),ie=new WeakMap;let fe=class{constructor(e,t,s){if(this._$cssResult$=!0,s!==G)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=e,this.t=t}get styleSheet(){let e=this.o;const t=this.t;if(F&&e===void 0){const s=t!==void 0&&t.length===1;s&&(e=ie.get(t)),e===void 0&&((this.o=e=new CSSStyleSheet).replaceSync(this.cssText),s&&ie.set(t,e))}return e}toString(){return this.cssText}};const Se=a=>new fe(typeof a=="string"?a:a+"",void 0,G),Te=(a,...e)=>{const t=a.length===1?a[0]:e.reduce((s,i,r)=>s+(n=>{if(n._$cssResult$===!0)return n.cssText;if(typeof n=="number")return n;throw Error("Value passed to 'css' function must be a 'css' function result: "+n+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(i)+a[r+1],a[0]);return new fe(t,a,G)},Ne=(a,e)=>{if(F)a.adoptedStyleSheets=e.map(t=>t instanceof CSSStyleSheet?t:t.styleSheet);else for(const t of e){const s=document.createElement("style"),i=L.litNonce;i!==void 0&&s.setAttribute("nonce",i),s.textContent=t.cssText,a.appendChild(s)}},ae=F?a=>a:a=>a instanceof CSSStyleSheet?(e=>{let t="";for(const s of e.cssRules)t+=s.cssText;return Se(t)})(a):a;/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */const{is:Re,defineProperty:Me,getOwnPropertyDescriptor:Pe,getOwnPropertyNames:ze,getOwnPropertySymbols:Oe,getPrototypeOf:Ie}=Object,j=globalThis,re=j.trustedTypes,He=re?re.emptyScript:"",De=j.reactiveElementPolyfillSupport,S=(a,e)=>a,q={toAttribute(a,e){switch(e){case Boolean:a=a?He:null;break;case Object:case Array:a=a==null?a:JSON.stringify(a)}return a},fromAttribute(a,e){let t=a;switch(e){case Boolean:t=a!==null;break;case Number:t=a===null?null:Number(a);break;case Object:case Array:try{t=JSON.parse(a)}catch{t=null}}return t}},ve=(a,e)=>!Re(a,e),ne={attribute:!0,type:String,converter:q,reflect:!1,useDefault:!1,hasChanged:ve};Symbol.metadata??=Symbol("metadata"),j.litPropertyMetadata??=new WeakMap;let x=class extends HTMLElement{static addInitializer(e){this._$Ei(),(this.l??=[]).push(e)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(e,t=ne){if(t.state&&(t.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(e)&&((t=Object.create(t)).wrapped=!0),this.elementProperties.set(e,t),!t.noAccessor){const s=Symbol(),i=this.getPropertyDescriptor(e,s,t);i!==void 0&&Me(this.prototype,e,i)}}static getPropertyDescriptor(e,t,s){const{get:i,set:r}=Pe(this.prototype,e)??{get(){return this[t]},set(n){this[t]=n}};return{get:i,set(n){const p=i?.call(this);r?.call(this,n),this.requestUpdate(e,p,s)},configurable:!0,enumerable:!0}}static getPropertyOptions(e){return this.elementProperties.get(e)??ne}static _$Ei(){if(this.hasOwnProperty(S("elementProperties")))return;const e=Ie(this);e.finalize(),e.l!==void 0&&(this.l=[...e.l]),this.elementProperties=new Map(e.elementProperties)}static finalize(){if(this.hasOwnProperty(S("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(S("properties"))){const t=this.properties,s=[...ze(t),...Oe(t)];for(const i of s)this.createProperty(i,t[i])}const e=this[Symbol.metadata];if(e!==null){const t=litPropertyMetadata.get(e);if(t!==void 0)for(const[s,i]of t)this.elementProperties.set(s,i)}this._$Eh=new Map;for(const[t,s]of this.elementProperties){const i=this._$Eu(t,s);i!==void 0&&this._$Eh.set(i,t)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(e){const t=[];if(Array.isArray(e)){const s=new Set(e.flat(1/0).reverse());for(const i of s)t.unshift(ae(i))}else e!==void 0&&t.push(ae(e));return t}static _$Eu(e,t){const s=t.attribute;return s===!1?void 0:typeof s=="string"?s:typeof e=="string"?e.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(e=>this.enableUpdating=e),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(e=>e(this))}addController(e){(this._$EO??=new Set).add(e),this.renderRoot!==void 0&&this.isConnected&&e.hostConnected?.()}removeController(e){this._$EO?.delete(e)}_$E_(){const e=new Map,t=this.constructor.elementProperties;for(const s of t.keys())this.hasOwnProperty(s)&&(e.set(s,this[s]),delete this[s]);e.size>0&&(this._$Ep=e)}createRenderRoot(){const e=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return Ne(e,this.constructor.elementStyles),e}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(e=>e.hostConnected?.())}enableUpdating(e){}disconnectedCallback(){this._$EO?.forEach(e=>e.hostDisconnected?.())}attributeChangedCallback(e,t,s){this._$AK(e,s)}_$ET(e,t){const s=this.constructor.elementProperties.get(e),i=this.constructor._$Eu(e,s);if(i!==void 0&&s.reflect===!0){const r=(s.converter?.toAttribute!==void 0?s.converter:q).toAttribute(t,s.type);this._$Em=e,r==null?this.removeAttribute(i):this.setAttribute(i,r),this._$Em=null}}_$AK(e,t){const s=this.constructor,i=s._$Eh.get(e);if(i!==void 0&&this._$Em!==i){const r=s.getPropertyOptions(i),n=typeof r.converter=="function"?{fromAttribute:r.converter}:r.converter?.fromAttribute!==void 0?r.converter:q;this._$Em=i;const p=n.fromAttribute(t,r.type);this[i]=p??this._$Ej?.get(i)??p,this._$Em=null}}requestUpdate(e,t,s,i=!1,r){if(e!==void 0){const n=this.constructor;if(i===!1&&(r=this[e]),s??=n.getPropertyOptions(e),!((s.hasChanged??ve)(r,t)||s.useDefault&&s.reflect&&r===this._$Ej?.get(e)&&!this.hasAttribute(n._$Eu(e,s))))return;this.C(e,t,s)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(e,t,{useDefault:s,reflect:i,wrapped:r},n){s&&!(this._$Ej??=new Map).has(e)&&(this._$Ej.set(e,n??t??this[e]),r!==!0||n!==void 0)||(this._$AL.has(e)||(this.hasUpdated||s||(t=void 0),this._$AL.set(e,t)),i===!0&&this._$Em!==e&&(this._$Eq??=new Set).add(e))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(t){Promise.reject(t)}const e=this.scheduleUpdate();return e!=null&&await e,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(const[i,r]of this._$Ep)this[i]=r;this._$Ep=void 0}const s=this.constructor.elementProperties;if(s.size>0)for(const[i,r]of s){const{wrapped:n}=r,p=this[i];n!==!0||this._$AL.has(i)||p===void 0||this.C(i,void 0,r,p)}}let e=!1;const t=this._$AL;try{e=this.shouldUpdate(t),e?(this.willUpdate(t),this._$EO?.forEach(s=>s.hostUpdate?.()),this.update(t)):this._$EM()}catch(s){throw e=!1,this._$EM(),s}e&&this._$AE(t)}willUpdate(e){}_$AE(e){this._$EO?.forEach(t=>t.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(e)),this.updated(e)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(e){return!0}update(e){this._$Eq&&=this._$Eq.forEach(t=>this._$ET(t,this[t])),this._$EM()}updated(e){}firstUpdated(e){}};x.elementStyles=[],x.shadowRootOptions={mode:"open"},x[S("elementProperties")]=new Map,x[S("finalized")]=new Map,De?.({ReactiveElement:x}),(j.reactiveElementVersions??=[]).push("2.1.2");/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */const Z=globalThis,oe=a=>a,W=Z.trustedTypes,de=W?W.createPolicy("lit-html",{createHTML:a=>a}):void 0,ge="$lit$",m=`lit$${Math.random().toFixed(9).slice(2)}$`,me="?"+m,Ue=`<${me}>`,y=document,N=()=>y.createComment(""),R=a=>a===null||typeof a!="object"&&typeof a!="function",Q=Array.isArray,Le=a=>Q(a)||typeof a?.[Symbol.iterator]=="function",V=`[
\f\r]`,k=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,le=/-->/g,ce=/>/g,_=RegExp(`>|${V}(?:([^\\s"'>=/]+)(${V}*=${V}*(?:[^
\f\r"'\`<>=]|("|')|))|$)`,"g"),he=/'/g,pe=/"/g,be=/^(?:script|style|textarea|title)$/i,We=a=>(e,...t)=>({_$litType$:a,strings:e,values:t}),c=We(1),A=Symbol.for("lit-noChange"),f=Symbol.for("lit-nothing"),ue=new WeakMap,$=y.createTreeWalker(y,129);function _e(a,e){if(!Q(a)||!a.hasOwnProperty("raw"))throw Error("invalid template strings array");return de!==void 0?de.createHTML(e):e}const je=(a,e)=>{const t=a.length-1,s=[];let i,r=e===2?"<svg>":e===3?"<math>":"",n=k;for(let p=0;p<t;p++){const o=a[p];let h,u,l=-1,v=0;for(;v<o.length&&(n.lastIndex=v,u=n.exec(o),u!==null);)v=n.lastIndex,n===k?u[1]==="!--"?n=le:u[1]!==void 0?n=ce:u[2]!==void 0?(be.test(u[2])&&(i=RegExp("</"+u[2],"g")),n=_):u[3]!==void 0&&(n=_):n===_?u[0]===">"?(n=i??k,l=-1):u[1]===void 0?l=-2:(l=n.lastIndex-u[2].length,h=u[1],n=u[3]===void 0?_:u[3]==='"'?pe:he):n===pe||n===he?n=_:n===le||n===ce?n=k:(n=_,i=void 0);const g=n===_&&a[p+1].startsWith("/>")?" ":"";r+=n===k?o+Ue:l>=0?(s.push(h),o.slice(0,l)+ge+o.slice(l)+m+g):o+m+(l===-2?p:g)}return[_e(a,r+(a[t]||"<?>")+(e===2?"</svg>":e===3?"</math>":"")),s]};class M{constructor({strings:e,_$litType$:t},s){let i;this.parts=[];let r=0,n=0;const p=e.length-1,o=this.parts,[h,u]=je(e,t);if(this.el=M.createElement(h,s),$.currentNode=this.el.content,t===2||t===3){const l=this.el.content.firstChild;l.replaceWith(...l.childNodes)}for(;(i=$.nextNode())!==null&&o.length<p;){if(i.nodeType===1){if(i.hasAttributes())for(const l of i.getAttributeNames())if(l.endsWith(ge)){const v=u[n++],g=i.getAttribute(l).split(m),b=/([.?@])?(.*)/.exec(v);o.push({type:1,index:r,name:b[2],strings:g,ctor:b[1]==="."?Ve:b[1]==="?"?qe:b[1]==="@"?Fe:B}),i.removeAttribute(l)}else l.startsWith(m)&&(o.push({type:6,index:r}),i.removeAttribute(l));if(be.test(i.tagName)){const l=i.textContent.split(m),v=l.length-1;if(v>0){i.textContent=W?W.emptyScript:"";for(let g=0;g<v;g++)i.append(l[g],N()),$.nextNode(),o.push({type:2,index:++r});i.append(l[v],N())}}}else if(i.nodeType===8)if(i.data===me)o.push({type:2,index:r});else{let l=-1;for(;(l=i.data.indexOf(m,l+1))!==-1;)o.push({type:7,index:r}),l+=m.length-1}r++}}static createElement(e,t){const s=y.createElement("template");return s.innerHTML=e,s}}function E(a,e,t=a,s){if(e===A)return e;let i=s!==void 0?t._$Co?.[s]:t._$Cl;const r=R(e)?void 0:e._$litDirective$;return i?.constructor!==r&&(i?._$AO?.(!1),r===void 0?i=void 0:(i=new r(a),i._$AT(a,t,s)),s!==void 0?(t._$Co??=[])[s]=i:t._$Cl=i),i!==void 0&&(e=E(a,i._$AS(a,e.values),i,s)),e}class Be{constructor(e,t){this._$AV=[],this._$AN=void 0,this._$AD=e,this._$AM=t}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(e){const{el:{content:t},parts:s}=this._$AD,i=(e?.creationScope??y).importNode(t,!0);$.currentNode=i;let r=$.nextNode(),n=0,p=0,o=s[0];for(;o!==void 0;){if(n===o.index){let h;o.type===2?h=new P(r,r.nextSibling,this,e):o.type===1?h=new o.ctor(r,o.name,o.strings,this,e):o.type===6&&(h=new Ge(r,this,e)),this._$AV.push(h),o=s[++p]}n!==o?.index&&(r=$.nextNode(),n++)}return $.currentNode=y,i}p(e){let t=0;for(const s of this._$AV)s!==void 0&&(s.strings!==void 0?(s._$AI(e,s,t),t+=s.strings.length-2):s._$AI(e[t])),t++}}class P{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(e,t,s,i){this.type=2,this._$AH=f,this._$AN=void 0,this._$AA=e,this._$AB=t,this._$AM=s,this.options=i,this._$Cv=i?.isConnected??!0}get parentNode(){let e=this._$AA.parentNode;const t=this._$AM;return t!==void 0&&e?.nodeType===11&&(e=t.parentNode),e}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(e,t=this){e=E(this,e,t),R(e)?e===f||e==null||e===""?(this._$AH!==f&&this._$AR(),this._$AH=f):e!==this._$AH&&e!==A&&this._(e):e._$litType$!==void 0?this.$(e):e.nodeType!==void 0?this.T(e):Le(e)?this.k(e):this._(e)}O(e){return this._$AA.parentNode.insertBefore(e,this._$AB)}T(e){this._$AH!==e&&(this._$AR(),this._$AH=this.O(e))}_(e){this._$AH!==f&&R(this._$AH)?this._$AA.nextSibling.data=e:this.T(y.createTextNode(e)),this._$AH=e}$(e){const{values:t,_$litType$:s}=e,i=typeof s=="number"?this._$AC(e):(s.el===void 0&&(s.el=M.createElement(_e(s.h,s.h[0]),this.options)),s);if(this._$AH?._$AD===i)this._$AH.p(t);else{const r=new Be(i,this),n=r.u(this.options);r.p(t),this.T(n),this._$AH=r}}_$AC(e){let t=ue.get(e.strings);return t===void 0&&ue.set(e.strings,t=new M(e)),t}k(e){Q(this._$AH)||(this._$AH=[],this._$AR());const t=this._$AH;let s,i=0;for(const r of e)i===t.length?t.push(s=new P(this.O(N()),this.O(N()),this,this.options)):s=t[i],s._$AI(r),i++;i<t.length&&(this._$AR(s&&s._$AB.nextSibling,i),t.length=i)}_$AR(e=this._$AA.nextSibling,t){for(this._$AP?.(!1,!0,t);e!==this._$AB;){const s=oe(e).nextSibling;oe(e).remove(),e=s}}setConnected(e){this._$AM===void 0&&(this._$Cv=e,this._$AP?.(e))}}class B{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(e,t,s,i,r){this.type=1,this._$AH=f,this._$AN=void 0,this.element=e,this.name=t,this._$AM=i,this.options=r,s.length>2||s[0]!==""||s[1]!==""?(this._$AH=Array(s.length-1).fill(new String),this.strings=s):this._$AH=f}_$AI(e,t=this,s,i){const r=this.strings;let n=!1;if(r===void 0)e=E(this,e,t,0),n=!R(e)||e!==this._$AH&&e!==A,n&&(this._$AH=e);else{const p=e;let o,h;for(e=r[0],o=0;o<r.length-1;o++)h=E(this,p[s+o],t,o),h===A&&(h=this._$AH[o]),n||=!R(h)||h!==this._$AH[o],h===f?e=f:e!==f&&(e+=(h??"")+r[o+1]),this._$AH[o]=h}n&&!i&&this.j(e)}j(e){e===f?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,e??"")}}class Ve extends B{constructor(){super(...arguments),this.type=3}j(e){this.element[this.name]=e===f?void 0:e}}class qe extends B{constructor(){super(...arguments),this.type=4}j(e){this.element.toggleAttribute(this.name,!!e&&e!==f)}}class Fe extends B{constructor(e,t,s,i,r){super(e,t,s,i,r),this.type=5}_$AI(e,t=this){if((e=E(this,e,t,0)??f)===A)return;const s=this._$AH,i=e===f&&s!==f||e.capture!==s.capture||e.once!==s.once||e.passive!==s.passive,r=e!==f&&(s===f||i);i&&this.element.removeEventListener(this.name,this,s),r&&this.element.addEventListener(this.name,this,e),this._$AH=e}handleEvent(e){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,e):this._$AH.handleEvent(e)}}class Ge{constructor(e,t,s){this.element=e,this.type=6,this._$AN=void 0,this._$AM=t,this.options=s}get _$AU(){return this._$AM._$AU}_$AI(e){E(this,e)}}const Ze=Z.litHtmlPolyfillSupport;Ze?.(M,P),(Z.litHtmlVersions??=[]).push("3.3.3");const Qe=(a,e,t)=>{const s=t?.renderBefore??e;let i=s._$litPart$;if(i===void 0){const r=t?.renderBefore??null;s._$litPart$=i=new P(e.insertBefore(N(),r),r,void 0,t??{})}return i._$AI(a),i};/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */const Y=globalThis;class T extends x{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){const e=super.createRenderRoot();return this.renderOptions.renderBefore??=e.firstChild,e}update(e){const t=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(e),this._$Do=Qe(t,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return A}}T._$litElement$=!0,T.finalized=!0,Y.litElementHydrateSupport?.({LitElement:T});const Ye=Y.litElementPolyfillSupport;Ye?.({LitElement:T});(Y.litElementVersions??=[]).push("4.2.2");class $e extends T{_config;_hass;_filter="all";_activeTab="none";static properties={_config:{state:!0},_hass:{state:!0},_filter:{state:!0},_activeTab:{state:!0}};static styles=Te`
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
  `;setConfig(e){this._config={title:"Australia and New Zealand Disaster Watch",max_incidents:10,show_map_button:!0,...e}}set hass(e){this._hass=e}getCardSize(){return 7}static getStubConfig(){return{type:"custom:ausnz-disaster-card",title:"Australia and New Zealand Disaster Watch",max_incidents:10,show_map_button:!0}}_findEntity(e){if(!this._hass)return null;if(this._config?.entity&&this._hass.states[this._config.entity])return this._hass.states[this._config.entity];const t=Object.keys(this._hass.states).find(s=>s.endsWith(e)||s.includes(e));return t?this._hass.states[t]:null}_getNearbyIncidents(){if(!this._hass)return[];const e=[],t="geo_location.";for(const[s,i]of Object.entries(this._hass.states))s.startsWith(t)&&i.attributes&&(i.attributes.source?.includes("Queensland")||i.attributes.source?.includes("Disaster")||i.attributes.source?.includes("NSW")||i.attributes.source?.includes("Vic")||i.attributes.source?.includes("Bureau")||i.attributes.source?.includes("New Zealand")||i.attributes.source?.includes("GeoNet")||i.attributes.source?.includes("NEMA")||i.attributes.source?.includes("MetService")||i.attributes.source?.includes("ausnz_disaster_watch")||i.attributes.source?.includes("australian_disaster_watch"))&&e.push({id:s,title:i.state||i.attributes.title||"Emergency Incident",hazard_type:i.attributes.hazard_type||"Other",warning_level:i.attributes.warning_level||"Information",distance_km:i.attributes.distance_km||i.attributes.distance,location_name:i.attributes.location_name,responsible_agency:i.attributes.responsible_agency||i.attributes.source,web_url:i.attributes.web_url,status:i.attributes.status,updated_at:i.attributes.updated_at});return e.sort((s,i)=>(s.distance_km??9999)-(i.distance_km??9999)),e}_toggleTab(e){this._activeTab=this._activeTab===e?"none":e}render(){if(!this._hass)return c`<ha-card><div class="empty-state">Loading...</div></ha-card>`;const e=this._findEntity("highest_warning_level"),t=this._findEntity("active_hazards_count"),s=this._findEntity("power_outages_count"),i=this._findEntity("road_closures_count"),r=this._findEntity("weather_warnings_count"),n=this._findEntity("fire_danger_rating"),p=this._findEntity("air_quality"),o=this._findEntity("primary_weather_observation"),h=this._findEntity("relief_facilities_count"),u=e?.state||"All Clear",l=t&&parseInt(t.state,10)||0,v=s&&parseInt(s.state,10)||0,g=i&&parseInt(i.state,10)||0,b=r&&parseInt(r.state,10)||0,ye=h&&parseInt(h.state,10)||0,K=s?.attributes?.customers_affected||0,J=s?.attributes?.outages||[],X=i?.attributes?.closures||[],ee=r?.attributes?.warnings||[],te=h?.attributes?.facilities||[];let z="banner-clear",O="ALL CLEAR — NO ACTIVE THREATS",I="🛡️";u==="Emergency Warning"?(z="banner-emergency",O="EMERGENCY WARNING IN REGION",I="🚨"):u==="Watch and Act"?(z="banner-watch-and-act",O="WATCH AND ACT IN REGION",I="⚠️"):u==="Advice"&&(z="banner-advice",O="ADVICE LEVEL ACTIVE",I="ℹ️");let C=this._getNearbyIncidents(),H=C;this._filter==="fire"?H=C.filter(d=>d.hazard_type.toLowerCase().includes("fire")):this._filter==="weather"?H=C.filter(d=>["flood","storm","cyclone"].some(w=>d.hazard_type.toLowerCase().includes(w))):this._filter==="road"&&(H=C.filter(d=>d.hazard_type.toLowerCase().includes("road")));const we=this._config?.max_incidents||10,se=H.slice(0,we),xe=o?.state!==void 0?`${o.state}°C`:"--",Ae=o?.attributes?.relative_humidity?`${o.attributes.relative_humidity}%`:"--",Ee=o?.attributes?.pressure_hpa?`${o.attributes.pressure_hpa} hPa`:"--",Ce=o?.attributes?.wind_speed_avg_kph?`${o.attributes.wind_speed_avg_kph} km/h`:"--",D=n?.state||"Moderate",ke=p?.state||"Good";return c`
      <ha-card>
        <div class="header">
          <div class="title">
            <span>🚨</span>
            <span>${this._config?.title||"Australia and New Zealand Disaster Watch"}</span>
          </div>
        </div>

        <div class="banner ${z}">
          <span>${I} ${O}</span>
          <span>${l} active hazards</span>
        </div>

        <!-- 4 Top Metric Tiles (Emergency News, Power Outages, Road Conditions, Weather Warnings) -->
        <div class="dashboard-tiles">
          <div
            class="dash-tile dash-tile-news ${this._activeTab==="news"?"active":""}"
            @click=${()=>this._toggleTab("news")}
          >
            <div class="dash-tile-title">
              <span>📰</span>
              <span>Emergency News</span>
            </div>
            <div class="dash-tile-value">
              <span>Active</span>
              <span class="dash-tile-sub">Bulletins</span>
            </div>
          </div>

          <div
            class="dash-tile dash-tile-power ${this._activeTab==="outages"?"active":""}"
            @click=${()=>this._toggleTab("outages")}
          >
            <div class="dash-tile-title">
              <span>⚡</span>
              <span>Power Outages</span>
            </div>
            <div class="dash-tile-value">
              <span>${v}</span>
              <span class="dash-tile-sub">(${K} affected)</span>
            </div>
          </div>

          <div
            class="dash-tile dash-tile-roads ${this._activeTab==="roads"?"active":""}"
            @click=${()=>this._toggleTab("roads")}
          >
            <div class="dash-tile-title">
              <span>🚧</span>
              <span>Road Conditions</span>
            </div>
            <div class="dash-tile-value">
              <span>${g}</span>
              <span class="dash-tile-sub">Closures</span>
            </div>
          </div>

          <div
            class="dash-tile dash-tile-weather ${this._activeTab==="warnings"?"active":""}"
            @click=${()=>this._toggleTab("warnings")}
          >
            <div class="dash-tile-title">
              <span>⛈️</span>
              <span>Weather Warnings</span>
            </div>
            <div class="dash-tile-value">
              <span>${b}</span>
              <span class="dash-tile-sub">BoM Alerts</span>
            </div>
          </div>
        </div>

        <!-- Quick Action Buttons -->
        <div class="quick-actions">
          <button
            class="action-btn ${this._activeTab==="telemetry"?"active":""}"
            @click=${()=>this._toggleTab("telemetry")}
          >
            <span>🌡️</span>
            <span>Conditions & AFDRS</span>
          </button>

          <button
            class="action-btn ${this._activeTab==="cameras"?"active":""}"
            @click=${()=>this._toggleTab("cameras")}
          >
            <span>📹</span>
            <span>Flood Cameras</span>
          </button>

          <button
            class="action-btn ${this._activeTab==="relief"?"active":""}"
            @click=${()=>this._toggleTab("relief")}
          >
            <span>🏠</span>
            <span>Relief & Evac (${ye})</span>
          </button>

          <button
            class="action-btn ${this._activeTab==="councils"?"active":""}"
            @click=${()=>this._toggleTab("councils")}
          >
            <span>🏛️</span>
            <span>Nearby Councils</span>
          </button>
        </div>

        <!-- Expandable Drawer for Active Tab -->
        ${this._activeTab!=="none"?c`
              <div class="drawer-content">
                ${this._activeTab==="news"?c`
                      <div class="drawer-header">
                        <span>📰 Emergency Bulletins & News</span>
                        <span class="drawer-close" @click=${()=>this._activeTab="none"}>✕</span>
                      </div>
                      <div class="detail-list">
                        <div class="detail-card">
                          <div class="detail-card-title">H5 Bird Flu Surveillance</div>
                          <div class="detail-card-meta">
                            Avoid, Record, Report sick or dead birds to the 24hr Emergency Animal Disease Hotline on 1800 675 888.
                          </div>
                        </div>
                        <div class="detail-card">
                          <div class="detail-card-title">Local Disaster Management Group Operational Update</div>
                          <div class="detail-card-meta">
                            All agencies on alert. Regular scheduled monitoring active across river catchments and road corridors.
                          </div>
                        </div>
                      </div>
                    `:""}

                ${this._activeTab==="outages"?c`
                      <div class="drawer-header">
                        <span>⚡ Power Outages (${v} active — ${K} customers affected)</span>
                        <span class="drawer-close" @click=${()=>this._activeTab="none"}>✕</span>
                      </div>
                      <div class="detail-list">
                        ${J.length===0?c`<div class="empty-state">No power outages reported in monitored area.</div>`:J.map(d=>c`
                                <div class="detail-card">
                                  <div class="detail-card-title">${d.suburb||"Local Suburb"} — ${d.cause}</div>
                                  <div class="detail-card-meta">
                                    Customers: ${d.customers_affected} • Estimated Restoration: ${d.restore_time||"Pending"}
                                  </div>
                                </div>
                              `)}
                      </div>
                    `:""}

                ${this._activeTab==="roads"?c`
                      <div class="drawer-header">
                        <span>🚧 Road Conditions & Closures (${g})</span>
                        <span class="drawer-close" @click=${()=>this._activeTab="none"}>✕</span>
                      </div>
                      <div class="detail-list">
                        ${X.length===0?c`<div class="empty-state">No road closures reported in monitored area.</div>`:X.map(d=>c`
                                <div class="detail-card">
                                  <div class="detail-card-title">${d.road} (${d.suburb||"Region"}) — ${d.status}</div>
                                  <div class="detail-card-meta">
                                    Reason: ${d.reason||"Hazard"} • Agency: ${d.source} ${d.advice?`• Advice: ${d.advice}`:""}
                                  </div>
                                </div>
                              `)}
                      </div>
                    `:""}

                ${this._activeTab==="warnings"?c`
                      <div class="drawer-header">
                        <span>⛈️ Bureau of Meteorology Warnings (${b})</span>
                        <span class="drawer-close" @click=${()=>this._activeTab="none"}>✕</span>
                      </div>
                      <div class="detail-list">
                        ${ee.length===0?c`<div class="empty-state">No weather warnings currently active.</div>`:ee.map(d=>c`
                                <div class="detail-card">
                                  <div class="detail-card-title">
                                    <a href="${d.link||"#"}" target="_blank" rel="noreferrer" style="color:inherit;text-decoration:underline;">
                                      ${d.title}
                                    </a>
                                  </div>
                                  <div class="detail-card-meta">Districts: ${d.locations||"Forecast Area"}</div>
                                </div>
                              `)}
                      </div>
                    `:""}

                ${this._activeTab==="telemetry"?c`
                      <div class="drawer-header">
                        <span>🌡️ Environmental Telemetry & Fire Danger</span>
                        <span class="drawer-close" @click=${()=>this._activeTab="none"}>✕</span>
                      </div>
                      <div class="telemetry-grid">
                        <div class="telemetry-card">
                          <div class="telemetry-card-label">Air Temp</div>
                          <div class="telemetry-card-val">${xe}</div>
                        </div>
                        <div class="telemetry-card">
                          <div class="telemetry-card-label">Humidity</div>
                          <div class="telemetry-card-val">${Ae}</div>
                        </div>
                        <div class="telemetry-card">
                          <div class="telemetry-card-label">Pressure</div>
                          <div class="telemetry-card-val">${Ee}</div>
                        </div>
                        <div class="telemetry-card">
                          <div class="telemetry-card-label">Wind Speed</div>
                          <div class="telemetry-card-val">${Ce}</div>
                        </div>
                        <div class="telemetry-card">
                          <div class="telemetry-card-label">Fire Danger (AFDRS)</div>
                          <span class="fdr-badge ${D.toLowerCase().includes("catastrophic")?"fdr-catastrophic":D.toLowerCase().includes("extreme")?"fdr-extreme":D.toLowerCase().includes("high")?"fdr-high":"fdr-moderate"}">${D}</span>
                        </div>
                        <div class="telemetry-card">
                          <div class="telemetry-card-label">Air Quality</div>
                          <div class="telemetry-card-val" style="color:#2e7d32;">${ke}</div>
                        </div>
                      </div>
                    `:""}

                ${this._activeTab==="cameras"?c`
                      <div class="drawer-header">
                        <span>📹 Live Flood & Traffic Webcams</span>
                        <span class="drawer-close" @click=${()=>this._activeTab="none"}>✕</span>
                      </div>
                      <div class="camera-grid">
                        <div class="camera-card">
                          <img class="camera-img" src="http://131940.qld.gov.au/img/WebCamImages/Metropolitan/Goodna_Ipswich_Mwy_East.jpg" alt="Goodna" />
                          <div class="camera-label">Goodna - Ipswich Mwy East</div>
                        </div>
                        <div class="camera-card">
                          <img class="camera-img" src="http://131940.qld.gov.au/img/WebCamImages/Metropolitan/Dinmore_Ipswich_Mwy_east.jpg" alt="Dinmore" />
                          <div class="camera-label">Dinmore - Ipswich Mwy East</div>
                        </div>
                        <div class="camera-card">
                          <img class="camera-img" src="http://131940.qld.gov.au/img/WebCamImages/NorthCoast/MRNC-0131.jpg" alt="Bruce Hwy" />
                          <div class="camera-label">Bruce Hwy - Caboolture</div>
                        </div>
                        <div class="camera-card">
                          <img class="camera-img" src="http://131940.qld.gov.au/img/WebCamImages/Metropolitan/MRMETRO-1218.jpg" alt="Metro" />
                          <div class="camera-label">Metropolitan Camera 1218</div>
                        </div>
                      </div>
                    `:""}

                ${this._activeTab==="relief"?c`
                      <div class="drawer-header">
                        <span>🏠 Disaster Relief Facilities</span>
                        <span class="drawer-close" @click=${()=>this._activeTab="none"}>✕</span>
                      </div>
                      <div class="detail-list">
                        ${te.length===0?c`<div class="empty-state">No open relief facilities or evacuations required at this time.</div>`:te.map(d=>c`
                                <div class="detail-card">
                                  <div class="detail-card-title">${d.name} (${d.suburb||"Region"})</div>
                                  <div class="detail-card-meta">Address: ${d.address||"Council Depot"} • Status: ${d.status}</div>
                                </div>
                              `)}
                      </div>
                    `:""}

                ${this._activeTab==="councils"?c`
                      <div class="drawer-header">
                        <span>🏛️ Connected Australian Disaster Dashboards</span>
                        <span class="drawer-close" @click=${()=>this._activeTab="none"}>✕</span>
                      </div>
                      <div class="council-links">
                        <a class="council-chip" href="https://disaster.moretonbay.qld.gov.au" target="_blank" rel="noreferrer">
                          <span>📍</span> City of Moreton Bay
                        </a>
                        <a class="council-chip" href="https://disasterhub.sunshinecoast.qld.gov.au" target="_blank" rel="noreferrer">
                          <span>📍</span> Sunshine Coast Regional Council
                        </a>
                        <a class="council-chip" href="https://disaster.brisbane.qld.gov.au" target="_blank" rel="noreferrer">
                          <span>📍</span> Brisbane City Council
                        </a>
                        <a class="council-chip" href="https://dashboard.cityofgoldcoast.com.au" target="_blank" rel="noreferrer">
                          <span>📍</span> City of Gold Coast
                        </a>
                        <a class="council-chip" href="https://disaster.noosa.qld.gov.au" target="_blank" rel="noreferrer">
                          <span>📍</span> Noosa Shire Council
                        </a>
                        <a class="council-chip" href="https://disaster.hawkesbury.nsw.gov.au" target="_blank" rel="noreferrer">
                          <span>📍</span> Hawkesbury City Council (NSW)
                        </a>
                        <a class="council-chip" href="https://emergency.bmcc.nsw.gov.au" target="_blank" rel="noreferrer">
                          <span>📍</span> Blue Mountains City Council (NSW)
                        </a>
                      </div>
                    `:""}
              </div>
            `:""}

        <!-- Filter Chips for Incident List -->
        <div class="filters">
          <div
            class="filter-chip ${this._filter==="all"?"active":""}"
            @click=${()=>this._filter="all"}
          >
            All Hazards (${C.length})
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

        <!-- Incidents List -->
        <div class="incidents-list">
          ${se.length===0?c`<div class="empty-state">
                No active incidents found in this filter within the monitored radius.
              </div>`:se.map(d=>{let w="badge-info",U="";return d.warning_level==="Emergency Warning"?(w="badge-emergency",U="emergency"):d.warning_level==="Watch and Act"?(w="badge-watch-act",U="watch-act"):d.warning_level==="Advice"&&(w="badge-advice",U="advice"),c`
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
                      <span class="badge ${w}">${d.warning_level}</span>
                      ${d.distance_km!==void 0?c`<span class="distance-tag">${d.distance_km} km</span>`:""}
                    </div>
                  </a>
                `})}
        </div>

        ${this._config?.show_map_button?c`
              <div class="footer">
                <a class="btn-map" href="/map">
                  <span>🗺️</span>
                  <span>View Incidents on Map</span>
                </a>
              </div>
            `:""}
      </ha-card>
    `}}customElements.get("ausnz-disaster-card")||customElements.define("ausnz-disaster-card",$e);customElements.get("aus-disaster-card")||customElements.define("aus-disaster-card",$e);window.customCards=window.customCards||[];window.customCards.push({type:"ausnz-disaster-card",name:"Australia and New Zealand Disaster Watch Card",description:"Real-time Australia and New Zealand Warning System disaster monitor and proximity hazard tracker.",preview:!0,documentationURL:"https://github.com/ruaandeysel/ha-australian-disaster-watch"});window.customCards.push({type:"aus-disaster-card",name:"Australia and New Zealand Disaster Watch Card (Legacy Alias)",description:"Real-time Australia and New Zealand Warning System disaster monitor and proximity hazard tracker.",preview:!1,documentationURL:"https://github.com/ruaandeysel/ha-australian-disaster-watch"});
