angular.module("filterService", [])

.factory("FilterService", function($location){

    var filters = {
      only_academic: "true",
      language: "python",
      tag: null,
      type: "pacakges"
    }

    var setFromUrl = function(){
      filters.only_academic = $location.search().only_academic
      filters.tag = $location.search().tag
      filters.language = $location.search().language
      filters.type = $location.search().type
      if (!filters.language){
        set("language", "python")
      }
      if (!filters.type){
        set("type", "people")
      }
      console.log("set filters from url", filters)
    }

    var set = function(k, v){
      filters[k] = v
      $location.search(k, v)
    }
    var toggle = function(k){
      // for booleans
      if (filters[k]) {
        filters[k] = null
      }
      else {
        filters[k] = "true"  // must be string or won't show up in url
      }
      $location.search(k, filters[k])
    }

    var unset = function(k){
      filters[k] = null
    }
    var unsetAll = function(){
        console.log("unset all!")
        _.each(filters, function(v, k){
            filters[k] = null
            $location.search(k, null)
        })
    }

    var asQueryStr = function(){
      var ret = []
      _.each(filters, function(v, k){
        if (v){
          ret.push(k + "=" + v)
        }
      })
      return ret.join("&")
    }


  return {
    d: filters,
    set: set,
    toggle: toggle,
    unset: unset,
    setFromUrl: setFromUrl,
    asQueryStr: asQueryStr,
    unsetAll: unsetAll
  }
});