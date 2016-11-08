(function() {
    var bookmarklet = {
        init: function() {
            $('a').remove();
            $('article').append($('<p>Bookmarklet loaded</p>'));
        }
    };

    if (typeof jQuery=='undefined') {
        console.log("no jquery. adding it.")
        jq = document.createElement( 'script' ); jq.type = 'text/javascript'; jq.async = true;
        jq.src = ('https:' == document.location.protocol ? 'https://' : 'http://') + 'ajax.googleapis.com/ajax/libs/jquery/3.1.1/jquery.min.js';
        jq.onload=bookmarklet.init;
        document.body.appendChild(jq);
    }
    else {
        console.log("looks like we've got jquery.")
        var $ = jQuery;
        bookmarklet.init();
    }
})();