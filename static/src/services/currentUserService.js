angular.module('currentUserService', [
])



    .factory("CurrentUser", function($http, $location){

      var data = {}

      function overWriteData(newData){
        _.each(newData, function(v, k){
          data[k] = v
        })
      }

      return {
        d: data,
        hasNoOrcid: function(){
          // the are loaded, but they have no ORCID. someone downstream prolly wants to fix this.
          return data.email && !data.orcid
        },
        get: function(){
          return $http.get("/api/me")
              .success(function(newData){
                overWriteData(newData)
                console.log("overwrote the CurrentUser data. now it's this:", data)

                // no matter where you are in the app, if you are logged in but have
                // no ORCID, it's time to fix that...you can't do anything else.
                if (!data.orcid) {
                  console.log("user has no ORCID! redirecting to landing page so they can fix that." )
                  $location.path("/")
                }
              })
              .error(function(resp){
                console.log("error getting current user data", resp)
              })
        }
      }


    })