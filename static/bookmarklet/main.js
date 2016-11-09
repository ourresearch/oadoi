// injected into the site by the oaDOI bookmarklet link.

(function() {


    // development settings and tools
    var devMode
    devMode = false
    devMode = true

    var baseUrl = "https://oadoi.org/static/bookmarklet/"
    if (devMode){
        baseUrl = "http://localhost:5001/static/bookmarklet/"
    }

    var devLog = function(str, obj){
        if (devMode){
            console.log("oaDOI: " + str, obj)
        }
    }

    var customAlert = function(str){
        alert(str)
    }




    // other config vars

    // from https://help.altmetric.com/support/solutions/articles/6000086842-getting-started-with-altmetric-on-your-journal-books-or-institutional-repository
    var doiMetaNames = [
        "citation_doi",
        "doi",
        "dc.doi",
        "dc.identifier.doi",
        "bepress_citation_doi",
        "rft_id"
    ]




    // templates
    var mainTemplate = "<div id='oaDOI-main' class='loading'>" +
            "<a id='oaDOI-logo-link' href='https://oadoi.org'><img src='https://oadoi.org/static/img/oadoi-logo-white.png'></a>" +
            "<div id='oaDOI-msg'>" +
                "<span id='oaDOI-msg-text'>Looking for open versions...</span> " +
            "</div>" +
            "<a href='' id='oaDOI-close-btn'>&#215;</a>" +
        "</div>"


    function reportResult(result){
        var errorReportLink = "<a href='' class='oaDOI-msg-report-error'>(report error)</a>"
        var results = {
            "no-doi": {
                msg: "Sorry, we couldn't find a DOI on this page."
            },
            "no-open-version": {
                msg: "Sorry, we couldn't find an open version of this article."
            },
            "viewing-open-version": {
                msg: "Looks like you're currently viewing an open-access version of this article."
            }
        }
        $("#oaDOI-msg-text").text(results[result].msg)
        $("#oaDOI-msg").append(errorReportLink)
        $("#oaDOI-main")
            .removeClass("loading")
            .addClass("has-result")
            .addClass("result-" + result)
        return true
    }



    function init() {
        devLog("running oaDOI bookmarklet.")
        // inject our markup.
        $(mainTemplate)
            .hide()
            .height("77px")
            .prependTo("body").click(function(){
                $(this).slideUp(100)
                return false
        })
            .slideDown(400)




        var doi = findDoi()
        console.log("doi:", doi)
        if (!doi){
            reportResult("no-doi")
        }
        var url = "https://api.oadoi.org/" + doi
        $.get(url, function(data){


            var resp = data.results[0]
            devLog("got data back from oaDOI", data)

            if (!resp.free_fulltext_url) {
                reportResult("no-open-version")
            }
            else if (resp.oa_color == "gold"){
                reportResult("viewing-open-version")
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


    // runs when you click the bookmarklet

    // inject our stylesheet
    var elem = document.createElement("link");
    elem.type = "text/css";
    elem.rel = "stylesheet";
    elem.href = baseUrl + "bookmarklet.css";
    var head = document.getElementsByTagName("head")[0]
    head.appendChild(elem);

    // load jquery
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