// Terugkeeradres voor de Authentik forward-auth, veilig ingepakt.
//
// De snippet forward-auth.conf stuurt een niet-ingelogde bezoeker naar
// /outpost.goauthentik.io/start?rd=<adres>. Zonder bewerking gaat het adres
// daar rauw in de query staan, en dan leest Authentik het maar tot aan de
// eerste &: alles na de eerste parameter valt weg en de bezoeker komt na het
// inloggen terug op een halve URL. Dat is geen fout van ons, de handleiding
// van Authentik schrijft het zo voor, maar hij klopt niet (14-08-2026, gezien
// bij het koppelen van de Postbus-connector).
//
// We coderen bewust alleen wat de query kan breken: & scheidt parameters, #
// begint een fragment, en % moet eerst omdat de andere twee er een
// introduceren. De rest laten we staan, zodat het adres leesbaar blijft in de
// logs en de domeincontrole van Authentik er gewoon een URL in ziet.
function terug(r) {
    var adres = r.variables.scheme + '://' + r.variables.http_host
                + r.variables.request_uri;
    return adres.replace(/%/g, '%25')
                .replace(/&/g, '%26')
                .replace(/#/g, '%23');
}

export default { terug };
