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
        get: function(){
          return $http.get("/api/me")
              .success(function(newData){
                overWriteData(newData)
                console.log("overwrote the CurrentUser data. now it's this:", data)

                if (!data.orcid) {
                  $location.path("/")
                }






              })
              .error(function(resp){
                console.log("error getting current user data", resp)
              })
        }
      }


    })