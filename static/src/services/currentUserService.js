angular.module('currentUserService', [
    'resourcesModule'
  ])



  .factory("CurrentUser", function(UserResource){

    var data = {}

    function overWriteData(newData){
      _.each(newData, function(v, k){
        data[k] = v
      })
    }

    return {
      d: data,
      get: function(){
        return UserResource.get(
          function(newData){
            overWriteData(newData)
            console.log("overwrote the CurrentUser data. now it's this:", data)
          },
          function(resp){
            console.log("error getting current user data", resp)
          }
        )
      }
    }


  })