// injected into the site by the oaDOI bookmarklet link.

(function() {

    // from https://help.altmetric.com/support/solutions/articles/6000086842-getting-started-with-altmetric-on-your-journal-books-or-institutional-repository
    var doiMetaNames = [
        "citation_doi",
        "doi",
        "dc.doi",
        "dc.identifier.doi",
        "bepress_citation_doi",
        "rft_id"
    ]

    var customAlert = function(str){
        alert(str)
    }

    function init() {
        console.log("running oaDOI bookmarklet.")

        var doi = findDoi()
        console.log("doi:", doi)
        if (!doi){
            customAlert("Sorry, we couldn't find a DOI on this page.")
        }
        var url = "https://api.oadoi.org/" + doi
        $.get(url, function(data){
            var resp = data.results[0]
            console.log("got data back from oaDOI", data)

            if (!resp.free_fulltext_url) {
                customAlert("Sorry, we couldn't find an open version of this article.")
            }
            else if (resp.oa_color == "gold"){
                customAlert("Looks like you're viewing an open access article right now.")
            }
            else {
                window.location.assign(resp.free_fulltext_url)
            }

        })


    }

    function findDoi(){
        var doiMetas = $("meta").filter(function(i, myMeta){
            return doiMetaNames.indexOf(myMeta.name.toLowerCase()) != -1
        })

        if (doiMetas.length && doiMetas[0].content){
            return doiMetas[0].content
        }
        else {
            return null
        }
    }

    if (typeof jQuery=='undefined') {
        console.log("no jquery. adding it.")
        jq = document.createElement( 'script' ); jq.type = 'text/javascript'; jq.async = true;
        jq.src = 'https://ajax.googleapis.com/ajax/libs/jquery/3.1.1/jquery.min.js';
        jq.onload=init();
        document.body.appendChild(jq);
    }
    else {
        console.log("looks like we've got jquery.")
        var $ = jQuery;
        init();
    }
})();