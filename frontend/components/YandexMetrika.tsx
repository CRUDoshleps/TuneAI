import Script from "next/script";

const counterId = process.env.NEXT_PUBLIC_YANDEX_METRIKA_ID?.trim() || "";
const enabled = /^\d+$/.test(counterId);

export default function YandexMetrika() {
  if (!enabled) return null;

  return (
    <>
      <Script id="yandex-metrika" strategy="afterInteractive">
        {`(function(m,e,t,r,i,k,a){m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)};m[i].l=1*new Date();for(var j=0;j<document.scripts.length;j++){if(document.scripts[j].src===r){return}}k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a)})(window,document,"script","https://mc.yandex.ru/metrika/tag.js?id=${counterId}","ym");ym(${counterId},"init",{ssr:true,clickmap:true,referrer:document.referrer,url:location.href,accurateTrackBounce:true,trackLinks:true,webvisor:false});`}
      </Script>
      <noscript>
        <div>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={`https://mc.yandex.ru/watch/${counterId}`}
            className="metrika-pixel"
            alt=""
            aria-hidden="true"
          />
        </div>
      </noscript>
    </>
  );
}
